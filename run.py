from gcloud_vertex import script
from configparser import ConfigParser
import argparse

config = ConfigParser()
config.read('config.ini')

parser = argparse.ArgumentParser(description='Batch pull patent details')

parser.add_argument('-m', '--model', type=str, default='gemini-2.5-flash',
                        help='Which model? gemini-3-flash-preview or gemini-2.5-flash')

args = parser.parse_args()
model = args.model

if model not in ['gemini-3-flash-preview', 'gemini-2.5-flash']:
    raise ValueError(f"Invalid model {model}. Must be either 'gemini-3-flash-preview' or 'gemini-2.5-flash'.")

script.run(config, model)
