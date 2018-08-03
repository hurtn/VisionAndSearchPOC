import platform
print("Python version: {0}".format(platform.python_version()))

import sys, os.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname( __file__ ), 'acmeenv/Lib/site-packages')))

import requests
import json
import time
import re
import os,sys
import httplib, urllib, base64
from datetime import datetime, timedelta
import base64
import hmac
import hashlib


# this section takes the input binding which is the filename in the message from the queue and returns a URL which we can pass to the Vision service
STORAGE_ACCOUNT_NAME = 'receiptstogo'
STORAGE_ACCOUNT_KEY = 'EVIFTsGJZ2AncYB7rhIQx/bIEJl32dXSC82KPDERL0bZPlj6YIy82Af5wmoemdVxIMmLNNcsenaY+53WjnYMkA=='
CONTAINER_NAME = 'image-drop'
AZURE_STORAGE_VERSION = "2015-12-11"

#read in the filename from the queue message
blob_name = open(os.environ['inputMessage']).read()

st= str(datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
se= str((datetime.utcnow() + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"))

iv = "{0}\n{1}\n{2}\n{3}\n{4}\n{5}\n{6}\n{7}\n{8}\n".format(
        STORAGE_ACCOUNT_NAME,   # 0. account name
        'r',                    # 1. signed permissions
        'b',                    # 2. signed service
        'o',                    # 3. signed resource type
        st,                     # 4. signed start time
        se,                     # 5. signed expire time
        '',                     # 6. signed ip
        'https',                # 7. signed protocol
        AZURE_STORAGE_VERSION)  # 8. signed version

# Create base64 encoded signature
hash =hmac.new(base64.b64decode(STORAGE_ACCOUNT_KEY),iv,hashlib.sha256).digest()
sig = base64.b64encode(hash)

querystring = {'sv':AZURE_STORAGE_VERSION,'ss':'b','srt':'o','sp':'r','se':se,'st':st,'spr':'https','sig':sig }

blob_url = "https://{0}.blob.core.windows.net/{1}/{2}?{3}".format(
         STORAGE_ACCOUNT_NAME,
         CONTAINER_NAME,
         blob_name,
         urllib.urlencode(querystring) )

print ("Blob SAS URL: " + blob_url)
#blob_url = urllib.quote(blob_url.encode('utf8'))
#print ("Encoded SAS URL: " + blob_url)

# Replace <Subscription Key> with your valid subscription key.
subscription_key = "4ba66f7ec8c448d59f1d55c4c6289d54"
assert subscription_key

# You must use the same region in your REST call as you used to get your
# subscription keys. For example, if you got your subscription keys from
# westus, replace "westcentralus" in the URI below with "westus".
#
# Free trial subscription keys are generated in the westcentralus region.
# If you use a free trial subscription key, you shouldn't need to change
# this region.
vision_base_url = "https://westus2.api.cognitive.microsoft.com/vision/v2.0/"

text_recognition_url = vision_base_url + "recognizeText"

# Set the request header information
headers = {'Content-Type': 'application/json','Ocp-Apim-Subscription-Key': subscription_key}

# set the request paramters
params  = {'mode': 'Printed'}
data    =  {"url": blob_url}

# make the request with the headers, parameters and json body
response = requests.post(
    text_recognition_url, headers=headers, params=params, json=data)
response.raise_for_status()

# Extracting handwritten or printed text requires two API calls: One call to submit the
# image for processing, the other to retrieve the text found in the image.

# Holds the URI used to retrieve the recognized text.
operation_url = response.headers["Operation-Location"]
#print(operation_url)

# The recognized text isn't immediately available, so poll to wait for completion.
analysis = {}
while "recognitionResult" not in analysis:
    response_final = requests.get(
        response.headers["Operation-Location"], headers=headers)
    analysis = response_final.json()
    time.sleep(1)

    


# In[4]:


#get the snippets of text from the image
snippets = [(line["boundingBox"], line["text"])
  for line in analysis["recognitionResult"]["lines"]]
#For this purpose assume store name is at the top of the receipt
store_name = (snippets[0][1])
print("Possible store name "+store_name)
#First try a specific search
store_search_url = "https://acme-demo-search.search.windows.net/indexes/azuresql-index/docs/search?api-version=2017-11-11"
search_headers = {'api-key':'E41B60B5AC5DE691B6DC2C9ABB1C2CEC'}

#override this for testing purposes
#store_name = "John Levis"

#define a function so that we can repeat the search if no match is found the first time
def search_stores (p_store):
    search_data = {  
      "search": p_store,
      "select": "Id, Store",
      "queryType": "full",  
      "searchMode": "all",
      "top": 1
      }
    search_response = requests.post(
        store_search_url, headers=search_headers, params=params, json=search_data)
    p_result = search_response.json()["value"]
    print(p_result) 
    return p_result

search_result = search_stores(store_name)
if search_result:
  print("Store is "+search_result[0]["Store"]+", ID "+search_result[0]["Id"])
  store_id = search_result[0]["Id"]
else:
  print("No match found, try fuzzy match")
  store_name = store_name.replace(" ", "~ ") + "~"
  search_result = search_stores(store_name)
  if search_result:
    print("Fuzzy match found store "+search_result[0]["Store"]+", ID "+search_result[0]["Id"])
    store_id = search_result[0]["Id"]
  else:
    print("Fuzzy match returned no results, use store ID 0")
    store_id = 0  
    
    
## Search for products    
# specify the search url 
product_search_url = "https://acme-demo-search.search.windows.net/indexes/azuresql-index-products/docs/search?api-version=2017-11-11"

#define a function so we can repeat the search if no match is found the first time
def search_products (p_product):
    search_prd_data = {  
      "search": p_product,
      "select": "Id, Product",
      "filter": "StoreId eq "+store_id,
      "top": 1
      }
    search_response = requests.post(
        product_search_url, headers=search_headers, params=params, json=search_prd_data)
    p_result = search_response.json()["value"]
    #print(p_result) 
    return p_result

regex = r".[\s-]*[\d]*[\s-]*(\.[\s-]*\d{2})"
for snippet in snippets:
    #if we find a match then the previous element may be a product name 
    if  re.search(regex, snippet[1]):
        print("Searching for product "+ previous_snippet)
        search_result = search_products(previous_snippet)
        if search_result:
            print("Product is "+search_result[0]["Product"]+", ID "+search_result[0]["Id"])
        else:
            print("Product could not be found ")

    else: #no match found keep track of the previous item
        previous_snippet = snippet[1]        
