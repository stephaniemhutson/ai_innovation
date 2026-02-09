from gcloud_vertex import script
from configparser import ConfigParser
import argparse

config = ConfigParser()
config.read('config.ini')

parser = argparse.ArgumentParser(description='Batch pull patent details')

parser.add_argument('-m', '--model', type=str, default='gemini-3-flash-preview',
                        help='Which model? gemini-3-flash-preview or gemini-2.5-flash')

args = parser.parse_args()
model = args.model

script.run(config, model)
