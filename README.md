# Minio Load Balancer <img src="./images/MINIO_Bird.png" alt="Minio Logo" width="20" height="20"/>

## This is a simple REST API that takes multiple instance of Minio and load balance them, between instances that are healthy.

- ### To run the application install the requirements with:
    - **pip install -r requirements.txt**
    - **Add for the first time your Minio instances in the config.json file in the format that is already presented in the file.**
    - **Then run python main.py**
- ### To see the postman collection for application download the Minio Load Balancer.postman_collection.json file and import it into postman to see how the requests are made.

### To build and run the application with Docker:
    - Go into main.py and change the line from load_balancer import MinIO to from load_balancer_docker import MinIO
    - Then run docker compose up -d to build the image and start the server
