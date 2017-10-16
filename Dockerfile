FROM clowder/pyclowder:2 as pyclowder2

From opendronemap/opendronemap

ENV MAIN_SCRIPT="opendrone_stitch.py"

RUN pip install pika \
    && pip install requests

COPY --from=pyclowder2 /usr/local/lib/python2.7/dist-packages/pyclowder/ /usr/local/lib/python2.7/dist-packages/pyclowder/
COPY entrypoint.sh *.py extractor_info.json /code/

ENTRYPOINT ["/code/entrypoint.sh"]
CMD ["extractor"]
