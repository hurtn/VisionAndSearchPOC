import platform
print("Python version: {0}".format(platform.python_version()))

import sys, os.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname( __file__ ), 'acmevenv/Lib/site-packages')))

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

########## Config required - enter your details in this section

# Enter your storage account name, key and container name here
STORAGE_ACCOUNT_NAME = '<storage account>'
STORAGE_ACCOUNT_KEY = '<storage key>'
CONTAINER_NAME = '<container name>'
AZURE_STORAGE_VERSION = "2015-12-11"

# Enter your store search url and api key
store_search_url = "<store search url>"
search_headers = {'api-key':'<search api key>'}

# Enter your product search url
product_search_url = "<product search url"

# Vision API configuration
# Replace <Subscription Key> with your valid subscription key.
subscription_key = "<Vision API Key>"
assert subscription_key

# You must use the same region in your REST call as you used to get your
# subscription keys. For example, if you got your subscription keys from
# westus, replace "westcentralus" in the URI below with "westus".
#
# Free trial subscription keys are generated in the westcentralus region.
# If you use a free trial subscription key, you shouldn't need to change
# this region.
vision_base_url = "https://westcentralus.api.cognitive.microsoft.com/vision/v2.0/"

############ end of config

#read in the filename from the queue message
blob_name = open(os.environ['inputMessage']).read()

#build the SAS URL
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

print ("Blob SAS URL created to access " + blob_name)

# Computer Vision

# Build the request to the vision service

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


# Extract the snippets of text from the image
snippets = [(line["boundingBox"], line["text"])
  for line in analysis["recognitionResult"]["lines"]]

# Search for store
# For this purpose assume store name is at the top of the receipt
store_name = (snippets[0][1])
print("Possible store name "+store_name)

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
    #print(p_result) 
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

regex = r".[\s-]*[\d]*[\s-]*(\.[\s-]*\d{2})"

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

previous_search = ''
previous_snippet =''
for snippet in snippets:
    #if we find a match then the previous element may be a product name 
    if  re.search(regex, snippet[1]) and \
        previous_snippet.find('TOTAL')<0  and \
        previous_snippet.find('CASH')<0 and \
        previous_snippet.find('3 FOR')<0:

        print("Searching for product "+ previous_snippet)
        
        if previous_snippet != previous_search: 
          search_result = search_products(previous_snippet)
          #sleep(10)
          previous_search = previous_snippet          

        if search_result:
            print("Product found: "+search_result[0]["Product"]+", ID "+search_result[0]["Id"])
        else:
            print("Product could not be found ")

    else: #no match found keep track of the previous item
        if snippet[1].isupper():
            previous_snippet = snippet[1]  
