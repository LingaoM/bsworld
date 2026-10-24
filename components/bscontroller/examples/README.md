# H4 HCI scanning example

English | [简体中文](README.zh-CN.md)

Install the component and retain `BSIM_OUT_PATH` from the BabbleSim build. From the component directory, run `python examples/advertise_scan.py`. The example exposes the scanning Controller as a Unix socket carrying standard H4 HCI packets. A mock Host connects to that socket, sends HCI initialization and passive-scanning commands, and reads an LE Advertising Report containing the expected address and data. The mock Host has no reference to the Controller object.

A second Controller supplies RF advertisements through the shared BabbleSim PHY. The example owns both Controllers, the PHY, its discrete Host clock, and a temporary HCI socket; it closes and removes these resources on exit.
