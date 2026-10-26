FROM node:22-bookworm@sha256:0e5f906573693feaa1e21057ebdcfdb5bd5021f050b2dc7c9deceb629c7da2a8
WORKDIR /app
COPY package.json server.js ./
COPY public ./public
COPY scripts ./scripts
COPY evidence ./evidence
ENV NODE_ENV=production PORT=10000 DATA_DIR=/var/data COLLECTION_INTERVAL_SECONDS=900
EXPOSE 10000
CMD ["python3", "scripts/production.py"]
