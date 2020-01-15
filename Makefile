schema_fname := game

.PHONY: all protobuf
all: protobuf

protobuf: $(schema_fname)_pb2.py

$(schema_fname)_pb2.py: $(schema_fname).proto
	protoc --python_out=src $<