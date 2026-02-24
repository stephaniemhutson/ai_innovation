from configparser import ConfigParser
# import google.generativeai as genai
from google.genai import types
from google import genai
import json
import time

from gcloud_vertex.bucket import Bucket


def get_client():
    config = ConfigParser()
    config.read('config.ini')
    api_key = config['GEMINI']['KEY']
    return genai.Client(
        # vertexai=True,
        # project=config['GCLOUD']['PROJECT_ID'],
        # location='us-central1'
        api_key=api_key
    )




class FileManager:
    def __init__(self, client):
        self.client = client

    def delete_file(self, file_name):
        confirmed = input(f"Are you sure you want to delete {file_name}? Y/n")
        if confirmed == "Y":
            self.client.files.delete(name=file_name)

    def delete_all_files(self):
        confirmed = input(f"Are you sure you want to delete all files? Y/n")
        if confirmed == "Y":
            for f in self.client.files.list():
                self.delete_file(f.name)

    def get_files(self):
        for i, f in enumerate(self.client.files.list()):
            print(f"{i}: {f.name}")
        return self.client.files.list()

    def get_file(self, filename=None):
        if not filename:
            files = self.get_files()

            file_number = input("Which file? (Give a number)")
            file_number = int(file_number)
            filename = files[file_number]

        file_contents = self.client.files.download(file=filename)

        return file_contents.decode('utf-8')



class JobManager:

    def __init__(self, client, model):
        self.client = client
        self.model = model
        self.__cached_content = None
        self.__bucket = Bucket('ai-innovation-output-bucket')
        self.filemanager = FileManager(client)

    # poll_for_jobs(client)
    def cancel_job(self, job_name):
        self.client.batches.cancel(name=job_name)
        print(f"Killed job {job_name}")

    def cancel_all_jobs(self):
        with open('gemini_jobs.txt', "r") as f:
            for line in f:
                job = line.split("\n")[0]
                cancel_job(job)

    def poll_for_job(self, job_name):

        print(f"Polling status for job: {job_name}")

        while True:
            batch_job = self.client.batches.get(name=job_name)
            if batch_job.state.name in ('JOB_STATE_SUCCEEDED', 'JOB_STATE_FAILED', 'JOB_STATE_CANCELLED', 'JOB_STATE_EXPIRED'):
                break
            print(f"Job not finished. Current state: {batch_job.state.name}. Waiting 30 seconds...")
            time.sleep(30)

        print(f"Job finished with state: {batch_job.state.name}")

        print(batch_job.dest)

        filename = batch_job.dest.file_name

        file_contents = self.filemanager.get_file(filename)

        with open(f"./data/outputs/{self.model}-{filename}", "w") as f:
            f.write(file_contents)
        # print the response
        # for i, inline_response in enumerate(batch_job_inline.dest.inlined_responses, start=1):
        #     print(f"\n--- Response {i} ---")

        #     # Check for a successful response
        #     if inline_response.response:
        #         # The .text property is a shortcut to the generated text.
        #         print(inline_response.response.text)

    def check_job(self, job_name):
        batch_job = self.client.batches.get(name=job_name)
        print(f"Job {job_name} state: {batch_job.state.name}")

    def check_all_jobs(self):
        with open('gemini_jobs.txt', "r") as f:
            for line in f:
                try:
                    job = line.split("\n")[0]
                    self.check_job(job)
                except (ValueError, genai.errors.ClientError):
                    # job removed
                    pass

    def __save_job_name(self, job_name):
        with open(f'gemini_jobs.txt', 'a') as f:
            f.write(job_name + '\n')

    def start_new_job(self, file_path):
        with open('system_instructions.txt', 'r', encoding='utf-8') as file:
            system_instructions = file.read()

        # generation_config = types.GenerateContentConfig(
        #     # It's recommended by Gemini to use a temperature of 1.0, however due to the
        #     # data analytic nature of this task and the desire for repeatability, it makes
        #     # sense to keep th temperature low. Because of the caution against using temperature
        #     # 0.0 due to some unintended consequences of the right token cannot be "found", I
        #     # have set the temperature to 0.1. In comparing the a spot check between temperature 0.1
        #     # and 0.0, there is relatively little variation.
        #     # temperature=0.1,
        #     # Because the context is designed to be fully descriptive of the task, we set the thinking
        #     # level to minimal. This minimized output tokens to less than 150 tokens per task, thus
        #     # minimizing the cost of API usage.
        #     max_output_tokens=200,
        #     thinking_config=types.ThinkingConfig(
        #         thinking_level="MINIMAL",
        #         # thinking_budget=100
        #     ),
        #     system_instruction=types.Content(
        #         parts=[
        #             types.Part(text= system_instructions)
        #         ]
        #     )
        # )

        file_name = file_path.split("/")[-1]
        if self.model == 'gemini-2.5-flash':
            uploaded_file = self.__bucket.upload_blob(file_path, file_name)

        elif self.model == 'gemini-3-flash-preview':
            uploaded_file = self.client.files.upload(
                file = file_path,
                config=types.UploadFileConfig(display_name='Innovation-test-jsonl', mime_type='application/jsonl')
            )

        print("Uploaded File:")
        print(uploaded_file.name)

        if self.model == 'gemini-2.5-flash':

            batch_job = self.client.batches.create(
                model=self.model,
                src=f"gs://{self.__bucket.bucket_name}/{file_name}",
                # src=uploaded_file.name,
                config=types.CreateBatchJobConfig(
                    display_name="AI Innovation-test",
                    # generation_config=generation_config
                    dest=f"gs://{self.__bucket.bucket_name}/output/{file_name}",
                ),
            )
        elif self.model == 'gemini-3-flash-preview':
            batch_job = self.client.batches.create(
                model=self.model,
                # src=f"gs://{self.__bucket.bucket_name}/{file_name}",
                src=uploaded_file.name,
                config=types.CreateBatchJobConfig(
                    display_name="AI Innovation-test",
                    # generation_config=generation_config
                    # dest=f"gs://{self.__bucket.bucket_name}/output/{file_name}",
                ),
            )

        print(f"Created batch job: {batch_job.name}")

        job_name = batch_job.name

        # save job name so it can be checked ig disconnected
        self.__save_job_name(job_name)

if __name__ == "__main__":
    task = input("""
        Which task would you like to do?
        [0] start new job
        [1] check on status of all jobs
        [2] check on status of one job
        [3] poll_for_job
        [4] File Manager
        [q] Exit
    """)
    if task[0] == "q":
        print("Goodbye")
    else:
        task = int(task[0])
        client = get_client()
        jmanager = JobManager(client)
        if task == 0:
            filepath = input("Where does your data come from? ")
            jmanager.start_new_job(filepath, 'gemini-3-flash-preview')
        elif task == 1:
            jmanager.check_all_jobs()
        elif task == 2:
            job = input("Input job name: ")
            jmanager.check_job(job)
        elif task == 3:
            job = input("Input job name: ")
            jmanager.poll_for_job(job)
        elif task == 4:
            filemanage = FileManager(client)
            task = input("""
                [0] Get Files
                [1] Get File
                [2] Delete Files
                [2] Delete one file
                """)
            task = int(task[0])
            if task == 0:
                filemanage.get_files()
            elif task == 1:
                filemanage.get_file()
            elif task == 2:
                filemanage.delete_all_files()
            elif task == 3:
                filename = input("Which file? ")
                filemanage.delete_file(filename)
        else:
            import pdb
            pdb.set_trace()

