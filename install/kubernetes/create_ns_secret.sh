
for namespace in 'infra' 'kubeflow' 'istio-system' 'pipeline' 'automl' 'jupyter' 'service' 'monitoring' 'logging' 'kube-system' 'aihub'
do
    kubectl create ns $namespace
    kubectl delete secret docker-registry hubsecret -n $namespace
    kubectl create secret docker-registry hubsecret --docker-server=https://index.docker.io/v1/ --docker-username=xxx --docker-password=xxxx -n $namespace
    kubectl label ns $namespace istio-injection=disabled --overwrite
#    kubectl label namespace $namespace istio-inhection=enabled --overwrite
done

kubectl label ns service istio-injection-


