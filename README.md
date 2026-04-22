# TutorBot Server

This application is designed as a TutorBot that can tutor anything
that can be expressed in text form. It is similar to a traditional
chatbot, but provides places to inject user-defined content.

Here are the key features:

1. A unique prompt parameter ordering that prevents the bot from
   drifting from its prompt intentions.
2. Prebuilt scenario, personality, conundrum, and action plan.
3. A conundrum file that defines content, restrictions, and permissions
   for whether the LLM can use its own content.
4. Prebuilt functionality to show users what content you are defining
   and what is provided by the LLM.

The design is simple and can be easily modified for different use
cases.

## Caveat

1. Conversational histories are maintained through the session's life.
   As they grow, they increase costs. Dropping previous conversations
   has downsides and needs to be factored in when needed.
2. Sessions are not cleared out. As they grow it could slow down
   processing, but that is unlikely for prototyping purposes.

## Prerequisites

### Create virtual environment

#### macOS and Linux

- Provision a virtual environment using the following command:

```bash
python -m venv .venv
```

- Activate the virtual environment you just provisioned:

```bash
source .venv/bin/activate
```

#### Windows for environment setup

- Provision a virtual environment using the following command:

```bash
python -m venv .venv
```

- Activate the virtual environment you just provisioned:

```bash
# In cmd.exe
.venv\Scripts\activate.bat
# In PowerShell
.venv\Scripts\Activate.ps1
```

- If you get this error message:

```bash
.venv\scripts\Activate.ps1 cannot be loaded because running
scripts is disabled on this system.
```

Run the command below in PowerShell with administrative privileges:

```bash
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Install dependencies

#### macOS and Linux for dependencies

- Install the dependencies by running:

```bash
python -m pip install -r ./requirements-unix.txt
```

#### Windows for dependencies

- Install the dependencies by running:

```bash
python -m pip install -r ./requirements-windows.txt
```

### Set up environment variables

To set the required secrets, duplicate `.env.example`, rename it to
`.env`, and fill its contents with the corresponding values. The
example environment variable file includes a brief description of each
variable.

## Run the TutorBot_Server development server

### macOS, Linux, and Windows for development server

To run the development server, follow these steps:

- Using the terminal, navigate to the root directory of this
  repository.
- Start the application by running:

```bash
python ./TutorBot_Server.py
```

- Open the application at `http://localhost:<PORT_FROM_ENV_VARS>`.

## Build executable bundles

### macOS, Linux, and Windows for executable bundles

To get an executable bundle that includes every necessary asset, follow
these steps:

- Using the terminal, navigate to the root directory of this
  repository.
- Build the executable by running:

```bash
pyinstaller TutorBot_Server.spec
```

- Copy all folders and files referenced in `TutorBot_Server.spec`
  under `a.datas` to the `dist` folder. Currently this is just the
  `static` folder.
- You can now move the `dist` folder or zip it and execute it from any
  directory where you want.

## Run the TutorBot_Server bundle

### From macOS and Linux

- Using the terminal, navigate to the `dist` directory.
- Run `./TutorBot_Server`.

### From Windows

- Using File Explorer, navigate to the `dist` directory.
- Double click `TutorBot_Server.exe`.

## Update requirements files after adding a dependency

There are two requirements files for Windows and Unix-based systems.
Every time you add a dependency, you should update these files by
running the following commands.

### macOS and Unix requirements update

```bash
python -m pip freeze > requirements-unix.txt
```

### Windows requirements update

```bash
python -m pip freeze > requirements-windows.txt --exclude enum34
```

## Contributors

This application was written by Michael Schmidt
<mike.schmidt@webmuffin.com> and Santiago Forero <biolimbo@pm.me>.
