FROM node:20-slim

WORKDIR /app

# Install package files
COPY package*.json ./
RUN npm install

# Copy source files
COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]
