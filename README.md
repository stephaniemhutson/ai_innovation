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
