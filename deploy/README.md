# Deployment Notes

## Container run (local)

```bash
cd /Users/fred/Desktop/IMC-Java-Code/python_research_platform
docker build -t qrt-platform:latest .
docker run --rm -e RUN_MODE=thread -e MAX_WORKERS=4 qrt-platform:latest
```

## AWS Batch concept

1. Build and push this image to ECR.
2. Create/update AWS Batch job definition referencing the image.
3. Submit jobs using `aws_batch_job.template.json` with your queue/definition names.

Example submit:

```bash
aws batch submit-job --cli-input-json file://deploy/aws_batch_job.template.json
```

## Reliability patterns in this project

- Job exits with non-zero code on failure.
- Structured logging via env-controlled log level.
- Atomic artifact writes for CSV/JSON to reduce partial files.
- Environment-driven runtime config for easy orchestration.
