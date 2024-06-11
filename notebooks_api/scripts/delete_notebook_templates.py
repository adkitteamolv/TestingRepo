import requests

request_headers = {
    "X-Auth-Userid": "swapnil.warule@fosfor.com",
    "X-Project-Id": "ee97bf13-dbe9-46d9-9281-a2b1a3762897",
    "X-Auth-Username": "swapnil.warule@fosfor.com",
    "X-Auth-Email": "swapnil.warule@fosfor.com"
}

template_names = ["Spark-3.6", "Spark-3.8", "Spark Distributed", "R-Jupyter", "Python-3.6", "Python-3.7", "RStudio-4",
                  "RStudio_RHEL-4.1", "Jupyterlab-3.6", "Jupyterlab-3.7", "R-Jupyterlab", "spark-Jupyterlab",
                  "VSCode-Scala2.12"]


def delete_template_data(image = ""):
    try:
        url = "http://notebooks-api:5000/notebooks/api/v1/docker-images/{}".format(image)
        resp = requests.delete(url, headers=request_headers)
        print("\nTemplate image deleted")
    except Exception as e:
        print("\nException")

url = "http://notebooks-api:5000/notebooks/api/v1/docker-images"
resp = requests.get(url, headers=request_headers)
output = resp.json()

delete_images = []
for item in output:
    if item["name"] in template_names:
        delete_images.append(item["id"])
        print(item["name"], item["id"])
print("\nImages to be deleted-", delete_images)

for image in delete_images:
    delete_template_data(image)

print("Completed")