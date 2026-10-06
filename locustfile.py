from locust import HttpUser, task, between


class CancerUser(HttpUser):
    wait_time = between(0.1, 0.3)

    @task
    def predict(self):
        self.client.post(
            "/v1/predict",
            json={
                "mean_radius": 17.99,
                "mean_texture": 10.38,
                "mean_perimeter": 122.8,
                "mean_area": 1001.0,
                "mean_smoothness": 0.1184,
                "mean_compactness": 0.2776,
            },
        )
