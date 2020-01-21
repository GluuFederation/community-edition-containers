### This example shows how to run Gluu Gateway Server

*__NOTE__* Some of the example files provided here are for test purposes only and they shouldn'be used in production.

### Prerequisites

- docker-compose
- Docker

### Instructions

- After cloning the repo, `cd examples/gluu-gateway`
- Fill out the rest of the information in the `.env` example file provided. Make sure there is a running instance of `oxd-server` because it it required by Gluu gateway server.
- run `docker-compose up`
- Wait for all the services to finish setting up and then go to your browser and open `https://localhost:1337` to access the UI. 