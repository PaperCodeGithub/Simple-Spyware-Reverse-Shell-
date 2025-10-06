# Panther — Ethical Remote Administration & Research Framework
## Important: 
This repository is intended only for lawful, ethical use — academic research, security testing in controlled environments, or internal IT/remote-support with explicit written consent from all parties/devices involved. Do not use this repository to access, monitor, or control devices without authorization. Misuse may be illegal and will not be supported.

## Overview

Panther is an educational remote administration and telemetry framework built for the purposes of:

1. Learning how remote agents and controllers communicate.
2. Building safe, auditable remote management tooling for IT teams.
3. Developing detection and defense techniques in an isolated lab environment.
4. Research and demonstration for security training and capture-the-flag (CTF) exercises.

This project must not be used to access systems without explicit written authorization from the system owner.

## Features

1. Simple client/server communication over configurable channels.
2. Command execution sandboxed to the local, isolated test environment.
3. Telemetry collection (system info, resource usage) for monitoring authorized hosts.
4. Structured audit logging of all commands and responses.
5. Extensible command architecture for adding new safe modules.

## Tech Stack

* **Language:** Python 3.8+
* **Database:** MongoDB (for storing authorized hosts, logs, telemetry in lab, command execution)
* **Libraries:** pymongo, CLI utilities
* **Environment:** Designed for Linux workstations/VMs in an isolated lab (recommended)

## Use Cases & Safety

* Classroom demonstrations of remote management protocols.
* Internal IT remote support for company-owned machines — with management approval.
* Penetration testing on systems with explicit scope and written authorization.
* Research into defensive detections and telemetry collection.

##  Quick Start (lab-only)
The commands below assume you have mongoDB ready env and all required python libraries
### Check host is online or not
```
deer-state
```
` Deer is connected ` means host is online

### Check host's system info
```
system-info
system-info -a hardware
system-info -a hardware internet
system-info -o hardware
system-info -o internet
```
`-a -> and`
`-o -> only`
This above commands will give you system and hardware info of host

### Enter host's shell
```
shell
```
Above code will push you into host's shell where you can have remote access to host's mechine
