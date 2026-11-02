FROM node:24-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# The development server. Week 5 replaces this with a built version for deployment.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
