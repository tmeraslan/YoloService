

#docker file YOLO


FROM python:3.10-slim-bullseye

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    YOLO_CONFIG_DIR=/tmp/Ultralytics

WORKDIR /app


RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libgl1 libsm6 libxext6 libxrender1 \
  && rm -rf /var/lib/apt/lists/*


RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
    torch torchvision


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir python-dotenv


COPY . .

RUN mkdir -p uploads/original uploads/predicted

ENV AWS_REGION=eu-west-1 \
    AWS_S3_BUCKET=tameer-yolo-images \
    AWS_S3_ADDRESSING_STYLE=path \
    AWS_S3_UNSIGNED=false

    
EXPOSE 8081
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8081"]







# FROM python:3.10-slim-bullseye
# WORKDIR /app
# COPY . .

# RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 libsm6 libxext6 libxrender1 && rm -rf /var/lib/apt/lists/*

# RUN pip install -r torch-requirements.txt
# RUN pip install -r requirements.txt


# CMD ["python", "app.py"]






# FROM python:3.10-slim-bullseye

# ENV PYTHONUNBUFFERED=1 \
#     PIP_NO_CACHE_DIR=1 \
#     YOLO_CONFIG_DIR=/tmp/Ultralytics

# WORKDIR /app

# RUN apt-get update && apt-get install -y --no-install-recommends \
#     libglib2.0-0 libgl1 libsm6 libxext6 libxrender1 \
#   && rm -rf /var/lib/apt/lists/*

# # Torch CPU
# RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
#     torch torchvision

# # deps
# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt \
#  && pip install --no-cache-dir python-dotenv

# # קוד
# COPY . .


# RUN mkdir -p uploads/original uploads/predicted

# # לא קובעים AWS_PROFILE כדי לא להפיל את הקונטיינר אם אין ~/.aws
# ENV AWS_REGION=eu-west-1 \
#     AWS_S3_BUCKET=tameer-yolo-images \
#     AWS_S3_ADDRESSING_STYLE=path

# EXPOSE 8084
# CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8084"]
















