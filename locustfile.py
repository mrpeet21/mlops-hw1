from locust import HttpUser, between, task


class CancerUser(HttpUser):
    wait_time = between(0.1, 0.3)

    @task
    def predict(self):
        self.client.post(
            "/v1/predict",
            headers={"Host": "cancer.localhost"},
            json={
                "mean_radius": 17.99,
                "mean_texture": 10.38,
                "mean_perimeter": 122.8,
                "mean_area": 1001.0,
                "mean_smoothness": 0.1184,
                "mean_compactness": 0.2776,
            },
        )
