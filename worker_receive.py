
#worker_receive.py
import os, os.path, json, uuid, time, logging, signal, sys
from urllib.parse import urlparse, urlunparse
import pika
from PIL import Image
from ultralytics import YOLO
import torch

# טען .env לפני os.getenv
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

from s3_utils import s3_or_http_download, s3_upload_file
import queries
from db import get_db

RABBIT_URL  = os.getenv("RABBIT_URL", "amqp://guest:guest@localhost:5672")
JOBS_QUEUE  = os.getenv("JOBS_QUEUE", "img_jobs")
RESULTS_EX  = os.getenv("RESULTS_EX", "img.results")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)

def _mask_amqp_url(amqp_url: str):
    p = urlparse(amqp_url)
    host = p.hostname or "localhost"
    port = p.port or 5672
    if p.username and p.password:
        netloc = f"{p.username}:***@{host}:{port}"
    else:
        netloc = p.netloc or f"{host}:{port}"
    return urlunparse((p.scheme, netloc, p.path, "", "", "")), host, port

masked_url, rabbit_host, rabbit_port = _mask_amqp_url(RABBIT_URL)
logging.info(f"[rabbit] RABBIT_URL={masked_url}")
logging.info(f"[rabbit] host={rabbit_host}, port={rabbit_port}, queues={JOBS_QUEUE}, results_ex={RESULTS_EX}")

torch.cuda.is_available = lambda: False
UPLOAD_DIR = "uploads/original"
PREDICTED_DIR = "uploads/predicted"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PREDICTED_DIR, exist_ok=True)
model = YOLO("yolov8n.pt")

def publish_result(result: dict, routing_key: str):
    """פרסום תוצאה ל-exchange ישירות (direct) עם routing_key = chatId."""
    params = pika.URLParameters(RABBIT_URL)
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    ch.exchange_declare(exchange=RESULTS_EX, exchange_type="direct", durable=True)
    ch.basic_publish(
        exchange=RESULTS_EX,
        routing_key=routing_key,
        body=json.dumps(result).encode("utf-8"),
        properties=pika.BasicProperties(
            delivery_mode=2, content_type="application/json"
        ),
    )
    conn.close()

def do_work(job: dict):
    uid = str(uuid.uuid4())
    ext = os.path.splitext(job["key"])[1] or ".jpg"
    original_path  = os.path.join(UPLOAD_DIR, uid + ext)
    predicted_path = os.path.join(PREDICTED_DIR, uid + ext)

    s3_url = f"s3://{job['bucket']}/{job['key']}"
    logging.info(f"[work] downloading {s3_url} -> {original_path}")
    if not s3_or_http_download(s3_url, original_path):
        raise RuntimeError(f"Failed to download {s3_url}")

    t0 = time.time()
    logging.info("[work] running YOLO...")
    results = model(original_path, device="cpu")
    Image.fromarray(results[0].plot()).save(predicted_path)
    took = round(time.time() - t0, 3)
    logging.info(f"[work] YOLO done in {took}s, saving to DB + S3...")

    db = next(get_db())
    queries.query_save_prediction_session(db, uid, original_path, predicted_path, "worker")

    labels = []
    for box in results[0].boxes:
        label = model.names[int(box.cls[0].item())]
        score = float(box.conf[0])
        bbox = box.xyxy[0].tolist()
        queries.query_save_detection_object(db, uid, label, score, str(bbox))
        labels.append(label)

    predicted_s3_key = f"worker/predicted/{uid}{ext}"
    _ = s3_upload_file(
        predicted_path,
        predicted_s3_key,
        extra_args={"Metadata": {"prediction_uid": uid, "user": "worker"}},
    )

    return {
        "prediction_uid": uid,
        "detection_count": len(results[0].boxes),
        "labels": labels,
        "time_took": took,
        "predicted_s3_key": predicted_s3_key,
    }

_shutdown = False
def _handle_sig(*_a):
    global _shutdown
    _shutdown = True
    logging.info("[worker] shutdown requested...")
signal.signal(signal.SIGINT, _handle_sig)
signal.signal(signal.SIGTERM, _handle_sig)

def main():
    global _shutdown
    while not _shutdown:
        try:
            logging.info(f"[rabbit] connecting to {masked_url} ...")
            params = pika.URLParameters(RABBIT_URL)
            conn = pika.BlockingConnection(params)
            ch = conn.channel()
            logging.info("[rabbit] connection established")

            q = ch.queue_declare(queue=JOBS_QUEUE, durable=True)
            ready = getattr(q.method, "message_count", None)
            logging.info(f"[rabbit] queue asserted: {JOBS_QUEUE} (ready={ready})")

            ch.basic_qos(prefetch_count=1)
            logging.info("[rabbit] QoS set: prefetch_count=1")

            def callback(chx, method, props, body):
                try:
                    logging.info(f" [x] Received job ({len(body)} bytes)")
                    job = json.loads(body.decode("utf-8"))
                    chat_id = job.get("chatId", "default-chat")
                    result = do_work(job)
                    # צירוף jobId לשקיפות
                    result_out = { **result, "jobId": job.get("jobId"), "chatId": chat_id }
                    publish_result(result_out, routing_key=chat_id)
                    chx.basic_ack(delivery_tag=method.delivery_tag)
                    logging.info(" [x] Done (acked + published result)")
                except Exception as e:
                    logging.exception(f"[job] failed: {e} -> NACK requeue")
                    chx.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

            ch.basic_consume(queue=JOBS_QUEUE, on_message_callback=callback, auto_ack=False)
            logging.info(f" [*] Waiting for messages on '{JOBS_QUEUE}'. To exit press CTRL+C")
            ch.start_consuming()
        except Exception as e:
            logging.exception(f"[worker] crash: {e}. retrying in 5s...")
            time.sleep(5)

    logging.info("[worker] exiting. bye 👋")
    sys.exit(0)

if __name__ == "__main__":
    main()
