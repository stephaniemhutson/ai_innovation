from configparser import ConfigParser
# import google.generativeai as genai
from google.genai import types
from google import genai
import json
import time

config = ConfigParser()
config.read('config.ini')

api_key = config['GEMINI']['KEY']


client = genai.Client(api_key=api_key)


class FileManager:
    def __init__(self, client):
        self.client = client

    def delete_file(self, file_name):
        self.client.files.delete(name=file_name)

    def delete_all_files(self):
        for f in self.client.files.list:
            delete_file(f.name)

    def get_files(client):
        for f in self.client.files.list():
            print(f.name)

def start_new_job(client):
    with open('system_instructions.txt', 'r', encoding='utf-8') as file:
        system_instructions = file.read()

    generation_config = types.GenerateContentConfig(
        # It's recommended by Gemini to use a temperature of 1.0, however due to the
        # data analytic nature of this task and the desire for repeatability, it makes
        # sense to keep th temperature low. Because of the caution against using temperature
        # 0.0 due to some unintended consequences of the right token cannot be "found", I
        # have set the temperature to 0.1. In comparing the a spot check between temperature 0.1
        # and 0.0, there is relatively little variation.
        # temperature=0.1,
        # Because the context is designed to be fully descriptive of the task, we set the thinking
        # level to minimal. This minimized output tokens to less than 150 tokens per task, thus
        # minimizing the cost of API usage.
        thinking_config=types.ThinkingConfig(
            thinking_level="minimal"
        ),
        system_instruction=types.Content(
        parts=[
            types.Part(text= system_instructions)
        ])
    )

    uploaded_file = client.files.upload(
        file = 'gemini_batch_input__scale.jsonl',
        config=types.UploadFileConfig(display_name='Innovation-test-jsonl', mime_type='application/jsonl')
    )

    print("Uploaded File:")
    print(uploaded_file.name)

    # output_config = types.BatchJobOutputConfig(
    #     gcs_destination=types.GcsDestination(
    #         uri="gs://your-bucket-name/output-folder/results.jsonl"
    #     )
    # )


    batch_job = client.batches.create(
        model='models/gemini-3-flash-preview',
        src=uploaded_file.name,
        # src="files/srj6sxbc8iud",
        config=types.CreateBatchJobConfig(
            display_name="AI Innovation-test",
            # generation_config=generation_config
        ),
        # dest=output_config
    )

    print(f"Created batch job: {batch_job.name}")

    def save_job_name(job_name):
        with open(f'gemini_jobs.txt', 'a') as f:
            f.write(job_name + '\n')

    def load_job_names():
        try:
            return int(open(f'data_batches/{batch_file}').read())
        except:
            return first_page


    job_name = batch_job.name

    # save job name so it can be checked ig disconnected
    save_job_name(job_name)


class JobManager:

    def __init__(self, client):
        self.client = client

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
            batch_job_inline = self.client.batches.get(name=job_name)
            if batch_job_inline.state.name in ('JOB_STATE_SUCCEEDED', 'JOB_STATE_FAILED', 'JOB_STATE_CANCELLED', 'JOB_STATE_EXPIRED'):
                break
            print(f"Job not finished. Current state: {batch_job_inline.state.name}. Waiting 30 seconds...")
            time.sleep(30)

        print(f"Job finished with state: {batch_job_inline.state.name}")



        # print the response
        for i, inline_response in enumerate(batch_job_inline.dest.inlined_responses, start=1):
            print(f"\n--- Response {i} ---")

            # Check for a successful response
            if inline_response.response:
                # The .text property is a shortcut to the generated text.
                print(inline_response.response.text)

    def check_job(self, job_name):
        batch_job_inline = self.client.batches.get(name=job_name)
        print(f"Job {job_name} state: {batch_job_inline.state.name}")

    def check_all_jobs(self):
        with open('gemini_jobs.txt', "r") as f:
            for line in f:
