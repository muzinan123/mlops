
import os,sys
import argparse
import datetime
import json
import shutil
import time
import uuid
import pysnooper
import re
import requests
import copy
import os
KFJ_CREATOR = os.getenv('KFJ_CREATOR', 'admin')
host = os.getenv('HOST',os.getenv('KFJ_MODEL_REPO_API_URL','http://kubeflow-dashboard.infra')).strip('/')

@pysnooper.snoop()
def download(**kwargs):
    # print(kwargs)
    headers = {
        'Content-Type': 'application/json',
        'Authorization': KFJ_CREATOR
    }
    model_path=""
    exist_model = {}
    # 从注册的模型中下载模型
    if kwargs['from']=='模型管理' or 'model' in kwargs['from']:
        url = host + "/training_model_modelview/api/?form_data=" + json.dumps({
            "filters": [
                {
                    "col": "name",
                    "opr": "eq",
                    "value": kwargs['model_name']
                },
                {
                    "col": "version",
                    "opr": "eq",
                    "value": kwargs['model_version']
                }
            ],
            "columns":['id','project','name','version','describe','path','framework','run_id','run_time','metrics','md5','api_type','pipeline_id']
        })

        # print(url)
        res = requests.get(url, headers=headers, allow_redirects=False)
        # print(res.content)
        if res.status_code == 200:
            exist_model = res.json().get('result', {}).get('data', [])
            if exist_model:
                exist_model = exist_model[0]
                print(exist_model)
                if exist_model['path']:
                    model_path = exist_model['path']
        else:
            print('访问平台获取模型失败')
            print(res.content)
            exit(1)

    elif kwargs['from']=='推理服务' or 'inference' in kwargs['from']:
        filters = [
            {
                "col": "model_name",
                "opr": "eq",
                "value": kwargs['model_name']
            },
            {
                "col": "model_version",
                "opr": "eq",
                "value": kwargs['model_version']
            }
        ]
        if kwargs['model_status']:
            filters.append({
                "col": "model_status",
                "opr": "eq",
                "value": kwargs['model_status']
            })


        url = host+"/inferenceservice_modelview/api/?form_data="+json.dumps({
            "filters":filters,
            "columns":  ['service_type','project', 'name', 'label','model_name', 'model_version', 'images', 'model_path', 'images', 'volume_mount','sidecar','working_dir', 'command', 'env', 'resource_memory',
                    'resource_cpu', 'resource_gpu', 'min_replicas', 'max_replicas', 'ports', 'inference_host_url','hpa','priority', 'canary', 'shadow', 'health','model_status','expand','metrics','deploy_history','host','inference_config']
        })

        # print(url)
        res = requests.get(url,headers=headers, allow_redirects=False)
        # print(res.content)
        if res.status_code==200:
            exist_service = res.json().get('result', {}).get('data', [])
            if exist_service:
                exist_service = exist_service[0]
                print(exist_service)
                if exist_service['model_path']:
                    model_path = exist_service['model_path']
        else:
            print('访问平台获取模型失败')
            print(res.content)
            exit(1)

    try:
        model_path=json.loads(model_path)
        model_path = model_path[kwargs['sub_model_name']]
    except Exception as e:
        pass
    if model_path:
        save_path = kwargs['save_path']
        os.makedirs(save_path, exist_ok=True)
        # 如果是在线地址，这下载
        if 'https://' in model_path or 'http://' in model_path:
            file_name = model_path.split("/")[-1]

            # 下载文件并保存到本地目录
            response = requests.get(model_path)
            with open(os.path.join(save_path, file_name), "wb") as file:
                file.write(response.content)
                file.close()

        elif not os.path.exists(model_path):
            print(f'{model_path}下不存在模型')
            exit(1)

        elif os.path.isdir(model_path):
            g = os.walk(model_path)
            for path, dir_list, file_list in g:
                for file_name in file_list:
                    one_file_path = os.path.join(path, file_name)
                    try:
                        des_path = os.path.join(save_path,file_name)
                        if os.path.exists(des_path):
                            os.remove(des_path)
                        shutil.copy2(one_file_path,des_path)
                    except Exception as e:
                        print(e)
        else:
            shutil.copy2(model_path,save_path)

        # 同时将模型信息写入到存储中,比如计算指标
        if kwargs['from']=='模型管理':
            if exist_model:
                json.dump(exist_model,open(os.path.join(save_path,f'{exist_model["name"]}.{exist_model["version"]}.json'),mode='w'))
    else:
        print('未发现模型')
        exit(1)


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser("download model launcher")
    arg_parser.add_argument('--from', type=str, help="模型来源地", default='train_model')
    arg_parser.add_argument('--model_name', type=str, help="模型名", default='demo')
    arg_parser.add_argument('--sub_model_name', type=str, help="子模型名", default='')
    arg_parser.add_argument('--model_version', type=str, help="模型版本号",default=datetime.datetime.now().strftime('v%Y.%m.%d.1'))
    arg_parser.add_argument('--model_status', type=str, help="模型状态", default='')
    arg_parser.add_argument('--save_path', type=str, help="下载目录", default='')

    args = arg_parser.parse_args()
    # print("{} args: {}".format(__file__, args))

    download(**args.__dict__)


