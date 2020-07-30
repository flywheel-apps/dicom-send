
# Local testing
Below are instructions for testing the functionality of this gear locally.

## Set up a local DICOM server.

Orthanc is an open-source, lightweight server. To download visit [Orthanc Server](https://www.osimis.io/en/download.html).

After downloading and setup, you can open a browser to visualize the DICOM exchange, via http://localhost:8042/app/explorer.html

- Once Orthanc is up and running, any imaging modality can send instances to Orthanc through the DICOM protocol (with the C-Store command). For example:
```
storescu -aec ORTHANC localhost 4242 *.dcm
```

- Orthanc can act both as a C-Store client (SCU) or as a C-Store server (SCP). In other words, it can either send or receive DICOM files. In the case of this Gear, we setup the server as the receiver. For more information, see the [Orthanc Server Book](https://book.orthanc-server.com/index.html
).


## Build the Image
To build the image:
```
    git clone https://github.com/flywheel-apps/dicom-send.git
    cd dicom-send
    docker build -t flywheel/dicom-send .
```

### Run the Image Locally
The dicom-send gear can be run locally with the following command.
```
docker run -it --rm \
    -v /path/to/config:/flywheel/v0/config.json \
    flywheel/dicom-send
```

The `-v` flag in the above command mounts a local config file to the correct path within the Docker container.

Below is the template of the local config file (JSON file), set with default Orthanc Server configuration:
```
{
  "config": {
      "destination": "<PLACE YOUR IP ADDRESS HERE>",
      "called_ae": "ORTHANC",
      "calling_ae": "flywheel",
      "port": 4242
  },
  "inputs": {
      "file": {
          "base": "file",
          "location": {"path": "/flywheel/v0/input/image1.dcm",
                       "name": "image1.dcm"}
      },
      "api_key": {
          "base": "api-key",
          "key": "<PLACE YOUR API KEY HERE>"
      }
  },
  "destination" : {
      "id" : "<PLACE YOUR SESSION ID HERE>"
  }
}
```

If you are testing locally, you have two options.

1. Input file to be passed into the Docker image; an example is provided here: dicom-send/tests/assets/image1.dcm
2. Set an API Key and Session ID, which also requires the creation of /flywheel/v0/input where the Gear will download DICOM data from the specified Session ID. This behavior is handled natively by Flywheel and is only required for local testing.
