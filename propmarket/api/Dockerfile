FROM node:20-alpine
WORKDIR /app
COPY package.json .
RUN npm install --production
COPY src/ ./src/
COPY public/ ./public/
# Migrations are mounted as a volume at runtime
EXPOSE 3002
CMD ["node", "src/index.js"]
