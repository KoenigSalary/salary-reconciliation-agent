# macOS Installation Guide

If you're encountering issues installing pandas on macOS, try these solutions:

## Solution 1: Use Pre-built Wheels (Recommended)

```bash
cd ~/Downloads/Agent/Reconciliation

# Upgrade pip first
pip3 install --upgrade pip setuptools wheel

# Install numpy first
pip3 install numpy==1.24.3

# Install pandas with pre-built wheel
pip3 install pandas==2.0.3

# Install remaining dependencies
pip3 install -r requirements.txt
```

## Solution 2: Install with Conda (If Available)

If you have Anaconda or Miniconda:

```bash
cd ~/Downloads/Agent/Reconciliation

# Create a new environment
conda create -n salary_recon python=3.10
conda activate salary_recon

# Install pandas via conda
conda install pandas=2.0.3

# Install remaining dependencies
pip install selenium==4.15.2 openpyxl==3.1.2 python-dateutil==2.8.2 webdriver-manager==4.0.1 schedule==1.2.0
```

## Solution 3: Install Xcode Command Line Tools

Sometimes the compilation fails due to missing build tools:

```bash
# Install Xcode command line tools
xcode-select --install

# Then try installing again
cd ~/Downloads/Agent/Reconciliation
pip3 install -r requirements.txt
```

## Solution 4: Use Homebrew Python

If you're using system Python, switch to Homebrew Python:

```bash
# Install Homebrew Python
brew install python@3.11

# Use Homebrew pip
/opt/homebrew/bin/pip3 install -r requirements.txt
```

## Solution 5: Install All at Once (Simplified)

```bash
cd ~/Downloads/Agent/Reconciliation

pip3 install --upgrade pip
pip3 install numpy pandas selenium openpyxl python-dateutil webdriver-manager schedule
```

## Solution 6: Use Python Virtual Environment

```bash
cd ~/Downloads/Agent/Reconciliation

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

## Verify Installation

After successful installation, test it:

```bash
cd ~/Downloads/Agent/Reconciliation
python3 -c "import pandas; import selenium; print('✓ All packages installed successfully!')"
```

## Still Having Issues?

Try installing packages one by one to identify the problem:

```bash
pip3 install numpy==1.24.3
pip3 install pandas==2.0.3
pip3 install selenium==4.15.2
pip3 install openpyxl==3.1.2
pip3 install python-dateutil==2.8.2
pip3 install webdriver-manager==4.0.1
pip3 install schedule==1.2.0
```

## Common macOS Issues

### Issue: "command 'clang' failed"
**Solution:** Install Xcode Command Line Tools
```bash
xcode-select --install
```

### Issue: "No module named '_lzma'"
**Solution:** Install xz
```bash
brew install xz
```

### Issue: "Architecture mismatch"
**Solution:** Reinstall Python with correct architecture
```bash
arch -arm64 brew install python@3.11  # For M1/M2 Macs
arch -x86_64 brew install python@3.11  # For Intel Macs
```

## Recommended: Use Virtual Environment

Always use a virtual environment to avoid system Python conflicts:

```bash
# Go to project
cd ~/Downloads/Agent/Reconciliation

# Create venv
python3 -m venv venv

# Activate
source venv/bin/activate

# Install
pip install --upgrade pip
pip install -r requirements.txt

# Run agent (always activate venv first)
source venv/bin/activate
python test_agent.py
```

## After Successful Installation

Once all packages are installed, proceed with:

```bash
cd ~/Downloads/Agent/Reconciliation
python3 test_agent.py
```

---

**Note:** If none of these solutions work, you may need to use a Docker container or a Linux VM for running the agent.
