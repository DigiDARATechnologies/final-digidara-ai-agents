# Adds pandas and numpy to Judge0's bundled Python 3.8.1 interpreter (Judge0
# language id 71 -- see agents/codeforge_agent/judge0/db/languages/active.rb:219,
# run_cmd: /usr/local/python-3.8.1/bin/python3 script.py) so the CodeForge
# Pandas/NumPy courses can run at all.
#
# The stock judge0/judge0:latest image (what agents/codeforge_agent/judge0/
# docker-compose.yml pulls, deliberately unmodified -- see this repo's root
# docker-compose.yml) ships a bare CPython 3.8.1 with no third-party
# packages. A student's submitted code runs with outbound network disabled
# (the gateway's judge0_client.py sets enable_network: False on every
# execution request), so nothing a submission does can install a package --
# it has to already be in the image before the submission ever runs.
#
# Versions are pinned to the last releases that still support Python 3.8
# (pandas dropped 3.8 support at 2.1, numpy at 1.25), matching the
# interpreter Judge0 actually executes.
FROM judge0/judge0:latest

USER root
RUN /usr/local/python-3.8.1/bin/python3 -m ensurepip --upgrade && \
    /usr/local/python-3.8.1/bin/python3 -m pip install --no-cache-dir pandas==2.0.3 numpy==1.24.4
USER judge0
