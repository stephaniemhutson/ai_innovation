# import google.generativeai as genai
from google import genai
from gcloud_vertex.cred_manager import load_creds
from configparser import ConfigParser

from gcloud_vertex.bucket import Bucket
import gemini_api

config = ConfigParser()
config.read('config.ini')

# creds = load_creds()
# genai.configure(credentials=creds)

# genai.list_models

BUCKET = "ai-innovation-output-bucket"

def run(config, model):

    if model == "gemini-2.5-flash":
        model = 'gemini-2.5-flash'
        client = genai.Client(
            vertexai=True,
            project=config['GCLOUD']['PROJECT_ID'],
            location='us-central1'
        )
        print("You are using Gemini 2.5 Flash and the GCloud Vertex API")
    else:
        model = 'gemini-3-flash-preview'
        client = genai.Client(
            api_key=config['GEMINI']['KEY']
        )
        print("You are using Gemini 3 Flash and the Gemini API")

    handle_inputs(client, model)


def handle_inputs(client, model):
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
        jmanager = gemini_api.JobManager(client, model)
        if task == 0:
            filepath = input("Where does your data come from? ")
            jmanager.start_new_job(filepath)
        elif task == 1:
            jmanager.check_all_jobs()
        elif task == 2:
            job = input("Input job name: ")
            jmanager.check_job(job)
        elif task == 3:
            job = input("Input job name: ")
            jmanager.poll_for_job(job)
        elif task == 4:
            filemanage = gemini_api.FileManager(client)
            task = input("""
                [0] Get Files
                [1] Get File
                [2] Delete Files
                [3] Delete one file
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

        handle_inputs(client, model)
