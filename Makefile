src_dir := src

schema_fname := game
proto_output := $(src_dir)/$(schema_fname)_pb2.py

requirements_file := $(src_dir)/requirements.txt

.PHONY: all build deploy deploy_local
all: deploy

build: $(proto_output) $(src_dir)/app.yaml $(requirements_file)

$(proto_output): $(schema_fname).proto
	protoc --python_out=src $<

$(requirements_file): poetry.lock
	poetry export -f requirements.txt -o $(requirements_file)

deploy: build
	@gcloud app deploy $(src_dir)/app.yaml

deploy_local:
	@cd $(src_dir) && \
	gunicorn -b :8080 main:web_app --worker-class aiohttp.GunicornUVLoopWebWorker