name: Feature Request
description: Suggest an idea for this project
title: "[FEATURE] "
labels: ["enhancement"]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for your interest in improving Open-Clip!
  - type: textarea
    id: problem
    attributes:
      label: Is your feature request related to a problem?
      description: Please describe what problem you are solving.
      placeholder: I'm always frustrated when...
    validations:
      required: true
  - type: textarea
    id: proposal
    attributes:
      label: Describe the solution you'd like
      description: A clear and concise description of what you want to happen.
      placeholder: I would like to be able to...
    validations:
      required: true
  - type: textarea
    id: alternatives
    attributes:
      label: Describe alternatives you've considered
      description: A clear and concise description of any alternative solutions or features you've considered.
