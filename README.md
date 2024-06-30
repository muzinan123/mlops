# mlops

# Infra
Currently mainly includes the following functions
 - 1、data management: feature store, online and offline features; dataset management, structure data and media data, data label platform
 - 2、develop: notebook(vscode/jupyter); docker image management; image build online
 - 3、train: pipeline drag and drop online; open template market; distributed computing/training tasks, example tf/pytorch/mxnet/spark/ray/horovod/kaldi/volcano; batch priority scheduling; resource monitoring/alarm/balancing; cron scheduling
 - 4、automl: nni, ray
 - 5、inference: model manager; serverless traffic control; tf/pytorch/onnx/tensorrt model deploy, tfserving/torchserver/onnxruntime/triton inference; VGPU; load balancing、high availability、elastic scaling
 - 6、infra: multi-user; multi-project; multi-cluster; edge cluster mode; blockchain sharing;

 
# Job Template

tips: 
- 1、You can develop your own template, Easy to develop and more suitable for your own scenarios

| template              | type | describe                                                                                     |
|:----------------------| :---- |:---------------------------------------------------------------------------------------------|
| linux                 | base | Custom stand-alone operating environment, free to implement all custom stand-alone functions | 
| datax                 | import export | Import and export of heterogeneous data sources                                              | 
| hadoop                | data processing | hdfs,hbase,sqoop,spark client                                                                |
| sparkjob              | data processing | spark serverless                                                                             |
| volcanojob            | data processing | volcano multi-machine distributed framework                                                  | 
| ray                   | data processing | python ray multi-machine distributed framework                                               |
| ray-sklearn           | machine learning | sklearn based on ray framework supports multi-machine distributed parallel computing         |
| xgb                   | machine learning | xgb model training and inference                                                             |
| tfjob                 | deep learning | Multi-machine distributed training of tensorflow                                             | 
| pytorchjob            | deep learning | 	Multi-machine distributed training of pytorch                                               | 
| horovod               | deep learning | 	Multi-machine distributed training of horovod                                               | 
| paddle                | deep learning | 	Multi-machine distributed training of paddle                                                | 
| mxnet                 | deep learning | 	Multi-machine distributed training of mxnet                                                 | 
| kaldi                 | deep learning | 	Multi-machine distributed training of kaldi                                                 | 
| tfjob-train           | model train | distributed training of tensorflow: plain and  runner                                        | 
| tfjob-runner          | model train | distributed training of tensorflow: runner method                                            | 
| tfjob-plain           | model train | distributed training of tensorflow: plain method                                             | 
| tf-model-evaluation   | model evaluate | distributed model evaluation of tensorflow2.3                                                | 
| tf-offline-predict    | model inference | distributed offline model inference of tensorflow2.3                                         | 
| model-register        | model service | register model to platform                                                                   | 
| model-offline-predict | model service | distributed offline model inference of framework                                             | 
| deploy-service        | model service | deploy inference service                                                                     | 
| media-download        | multimedia data processing | 	Distributed download of media files                                                         | 
| video-audio           | multimedia data processing | 	Distributed extraction of audio from video                                                  | 
| video-img             | multimedia data processing | Distributed extraction of pictures from video                                                | 
| yolov7                | machine vision | object-detection with yolov7                                                                 |
