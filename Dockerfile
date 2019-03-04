
FROM opendronemap/odm

ENV MAIN_SCRIPT="opendrone_stitch.py"

RUN pip install pika \
    && pip install --ignore-installed requests pyclowder

    COPY entrypoint.sh *.py extractor_info.json /code/

ENTRYPOINT ["/code/entrypoint.sh"]
CMD ["extractor"]
