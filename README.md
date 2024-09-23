# birdnet-lite-demo

## Instructions
Authors: Dhanuj Gandikota


### Birdnet Docker

#### Details

Runs on Raspberry Pi 5 with Raspberry OS Lite

This dockerfile was initially created to demo the Birdnet capabilities of an audio sensor. This will run birdnet in the background (with an assumption it is running for Austin, Texas), and will also bring up a png for each new bird that is identified within the ledger. 

Designed to run continously in background.

Upon initial run will
1. Ask if you want to overwrite previous run results (good for demos)
2. Ask which connected Audio device you want to use for the microphone

Only the latest five recordings are kept and audio files are deleted after they are converted into ledger information csv. 

All the hyperparameters are adjustable within the main.py.

#### Run and Build the Docker

Go to the code folder
```
docker build -t birdnet_pi .
```
```
docker run --rm -it     --device /dev/snd     --group-add audio     -v /home/dgandikota/output_test:/home/dgandikota/output_test     birdnet_pi
```


### Other Instructions

1. Enter Raspberry Pi Config to set the wifi system up.
```
sudo raspi-config
```
2. Check which port the raspberry pi is registered on
```
arp -a | grep raspberry
```
3. ssh into raspberry at that port
4. Double Check which SSID the raspberry pi is connected to
```
iwgetid
```