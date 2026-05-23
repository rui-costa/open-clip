name: Bug Report
description: Report a bug to help us improve Open-Clip
title: "[BUG] "
labels: ["bug"]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for taking the time to fill out this bug report!
  - type: input
    id: contact
    attributes:
      label: Contact Details
      description: How can we reach you if we need more info? (optional)
      placeholder: ex. email@example.com
  - type: textarea
    id: description
    attributes:
      label: Description
      description: A clear and concise description of what the bug is.
      placeholder: Tell us what is happening.
    validations:
      required: true
  - type: textarea
    id: reproduction
    attributes:
      label: Steps to Reproduce
      description: How can we trigger the issue?
      placeholder: |
        1. Go to '...'
        2. Click on '....'
        3. Scroll down to '....'
        4. See error
    validations:
      required: true
  - type: textarea
    id: environment
    attributes:
      label: Environment
      description: Tell us about your setup.
      placeholder: |
        - OS: [e.g. macOS]
        - Docker version: [e.g. 20.10.x]
        - Browser: [e.g. Chrome, Firefox]
    validations:
      required: true
  - type: textarea
    id: logs
    attributes:
      label: Relevant Logs or Screenshots
      description: Add any relevant logs, error messages, or screenshots here.
