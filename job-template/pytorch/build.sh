#!/bin/bash

set -ex

docker build -t ccr.ccs.tencentyun.com/cube-studio/pytorch:20230801 -f job/pytorch/Dockerfile .
docker push ccr.ccs.tencentyun.com/cube-studio/pytorch:20230801


