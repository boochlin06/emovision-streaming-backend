
# docker exec -it gateway bash
docker exec -it $(docker ps |grep 'emovision-streaming_gateway_1' | awk '{print $1}') bash