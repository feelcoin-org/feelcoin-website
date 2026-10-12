# Feelcoin Deployment Isolation

## Main website
- Domain: feelcoin.org
- Production root: /var/www/feelcoin.online
- Approved source: this repository
- Publisher: deployment/guarded-publish.py

## Node dashboards
- node1.feelcoin.org
- node2.feelcoin.org
- Repository: feelcoin-org/feelcoin-node-dashboard

The main website publisher must never target node directories.

Node dashboard deployments must never target the main website.

Always preserve the production version before deployment.
