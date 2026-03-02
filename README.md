# AI Innovation

## Set up

```
 python3 -m venv .env
 source .env/bin/activate
 pip install -r requirements.txt
 ```

## gcloud auth
```
gcloud auth application-default login
    --no-browser
    --client-id-file=client_secret.json
    --scopes='https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/generative-language.retriever'
```

## STEPS

Be sure to update all file names within the relavent files to

1. Pull patents -- Estimated time a few hours
```
python patents_api.py
```
choose option  `[2]  get_all_patents`

2. Pull patent abstracts for granted patents -- Estimated time a few hours

```
python patents_api.py
```

3. Remove patents which are clearly not on the AI frontier, for instance use clearly medical terms or application terms in the patent title. Update file names as necessary.

```
python post_filter.py
```

choose option  `[6]  get_patent_abstracts__uspto`

4. Pull patent/application abstracts, backgrounds and summaries -- Estimated time: Several days to over a week. It is recommend batching using add args. Current batch size is set to 100. If you change the batch size mid extraction, make sure to adjust first and last pages as well.

```
python patents_api.py -f {<str> file name for keeping track of which page you're on} -fp {<int> first page to start on} -lp {<int> last page to finish on}
```
Choose option `[1] batch_pull_details`

5. Move all files `patents_with_details__{page}.csv` into a folder for use in `post_collection_filter.py`

6. Filter out patents that don't have enough information in them - eg fewer than 400 character. Adjust files as needed. Estimated time: seconds.

```
python post_collection_filter.py
```

7. Create inputs. This uses predefined system instructions to tell the LLM what to do. Estimated time: seconds.

```
python create_inputs.py
```
Input which model you want to use -- gemini 2.5 or 3
If you have already made you inputs and want to make sure that you are not overwritting them, update the offset in your jsonl path defined in `convert_csv_to_jsonl` (as of 3/2/2026 this is on line 213)

8. Hit the Gemini API (or vertex API if using GEMINI 2.5) to begin batch processing of inputs. Estimated time: 24 hours per the conditions of Gemini's batch interface.

_Recommendation:_ Make a small batch file of inputs and test it first, especially if you are using Gemini 3 since the project wound up using Gemini 2.5.

```
python run.py -m {<str> model name, one of gemini-3-flash-preivew or gemini-2.5-flash. Default: 2.5
```

For each batch input jsonl file, select option `[0] start a new job` and supply the path to the batch file.

9. Clean outputs. Adujst the filenames at the top of the file for which outputs to clean.

```
python clean_outputs.py
```

10. Get citations for applications and patents as best as you can.
Note that the citaions count is biased towards older patents - when looking at a longer time frame than the 8 years of this study, you should be safe for patents greater than 5 years old, but due to the recency of the patents, we see a considerable bias.

`python patents_api.py`

 * Select option `[3] get_patent_citations_from_big_list`  -- Hits the USPTO api which only collects data on granted patents, but should be considered more complete then option `[5]`. Accepts argument `-b` which allows you to pick up where you left off if you get disconnected. Estimated time: A few hours.

 * Select option `[5] get_patents_count` -- Uses a wider master list of patents which are not filtered nearly as much and has information about cited patent applications. Accepts argument `-b` which allows you to pick up where you left off if you get disconnected. Estimated time: A few hours.

 Then select option `[4] get_application_patent_numbers` -- Crosswalks between the document numbers which are found in the above step and matches them to application numbers.

11. Clean the citations and merge with the rest of the data.

```python citations.py```
