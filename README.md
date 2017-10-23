Extractor to stitch drone images
=================================================

This is a Clowder extractor to stitch drone images into one image using OpenDroneMap.

## Build
```
docker build -t clowder/extractors-opendronemap .
```
## How to Run
1. start docker container
```
docker run --name=opendronemap-py2 -d --restart=always -e 'RABBITMQ_URI=amqp://user1:pass1@rabbitmq.ncsa.illinois.edu:5672/clowder-dev' -e 'RABBITMQ_EXCHANGE=clowder' -e 'TZ=/usr/share/zoneinfo/US/Central' -e 'REGISTRATION_ENDPOINTS=http://clowderhostname:9000/api/extractors?key=key1' clowder/extractors-opendronemap
```
2. login clowder and create dataset. And then upload images into dataset. Finally, upload extractors-opendronemap.txt to trigger opendronemap extractor to do stitching.

3. Upon completion, .tif file will be shown in the dataset.

Suggest allocate 10GB memory for docker run.
