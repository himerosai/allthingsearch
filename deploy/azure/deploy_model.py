from azure.ai.ml import MLClient
from azure.ai.ml.entities import (
    ManagedOnlineEndpoint,
    ManagedOnlineDeployment,
    Model,
    Environment,
    CodeConfiguration,
)
from azure.ai.ml.entities import Workspace
import time
from azure.mgmt.resource import ResourceManagementClient
from azure.identity import (
    DefaultAzureCredential,
    InteractiveBrowserCredential,
    ClientSecretCredential,
)
from azure.ai.ml import MLClient
from azure.identity import DefaultAzureCredential

from config import *
# authenticate
credential = DefaultAzureCredential()

try:
    credential = DefaultAzureCredential()
    credential.get_token("https://management.azure.com/.default")
except Exception as ex:
    credential = InteractiveBrowserCredential()

# Obtain the management object for resources.
resource_client = ResourceManagementClient(credential, subscription_id)

# Provision the resource group.
rg_result = resource_client.resource_groups.create_or_update(
    "3dsearch-rg", {"location": location}
)

print(
    f"Provisioned resource group {rg_result.name} in the {rg_result.location} region"
)


# Within the ResourceManagementClient is an object named resource_groups,
# which is of class ResourceGroupsOperations, which contains methods like
# create_or_update.
#
# The second parameter to create_or_update here is technically a ResourceGroup
# object. You can create the object directly using ResourceGroup(location=
# LOCATION) or you can express the object as inline JSON as shown here. For
# details, see Inline JSON pattern for object arguments at
# https://learn.microsoft.com/azure/developer/python/sdk
# /azure-sdk-library-usage-patterns#inline-json-pattern-for-object-arguments


ml_client = MLClient(
    credential,
    subscription_id=subscription_id,
    resource_group_name="3dsearch-rg",
    workspace_name=workspace_name
)


ws_basic = Workspace(
    name=workspace_name,
    location=location,
    display_name="3d search workspace",
    description="This example shows how to create a basic workspace",
    hbi_workspace=False,
    tags=dict(purpose="test"),
)

ws_basic = ml_client.workspaces.begin_create(ws_basic).result()

print(ws_basic)

model_id = f"azureml://registries/{registry_name}/models/{model_name}/labels/latest"

# endpoint name must be unique per Azure region, hence appending timestamp

ml_client.begin_create_or_update(ManagedOnlineEndpoint(name=endpoint_name) ).wait()

ml_client.online_deployments.begin_create_or_update(ManagedOnlineDeployment(
    name=endpoint_name,
    endpoint_name=endpoint_name,
    model=model_id,
    instance_type=instance_type,
    instance_count=1,
)).wait()

endpoint = ml_client.online_endpoints.get(endpoint_name)
endpoint.traffic = {"test": 100}

result = ml_client.begin_create_or_update(endpoint).result()

# print a selection of the endpoint's metadata
print(
    f"Name: {endpoint.name}\nStatus: {endpoint.provisioning_state}\nDescription: {endpoint.description}"
)

# existing traffic details
print(endpoint.traffic)

# Get the scoring URI
print(endpoint.scoring_uri)

logs = ml_client.online_deployments.get_logs(
    name="test", endpoint_name=endpoint_name, lines=10
)

print(logs)
