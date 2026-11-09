FROM modelscope-registry.cn-beijing.cr.aliyuncs.com/modelscope-repo/python:3.10

WORKDIR /home/user/app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MEMORY_HOST=0.0.0.0 \
    MEMORY_PORT=7860

COPY ./ /home/user/app

# The workbench runtime is standard-library only; no pip install is required.
RUN python -m compileall -q memlab memwb server.py

EXPOSE 7860

ENTRYPOINT ["python", "-u", "server.py"]
