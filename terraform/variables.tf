variable "aws_region" {
  description = "The AWS region to deploy resources in"
  type        = string
  default     = "us-west-2"
}

variable "project_name" {
  description = "Name of the project, used as prefix for resource names"
  type        = string
  default     = "doc-summarizer"
}

variable "environment" {
  description = "Environment (e.g., dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "vpc_id" {
  description = "ID of the VPC where resources will be deployed"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for Lambda and ElastiCache deployment"
  type        = list(string)
}

variable "api_handler_zip_path" {
  description = "Path to the zipped Lambda code for the API handler"
  type        = string
  default     = "api_handler.zip"
}

variable "processor_zip_path" {
  description = "Path to the zipped Lambda code for the processor"
  type        = string
  default     = "processor.zip"
}

variable "grokx_api_key" {
  description = "API key for the GrokX LLM service"
  type        = string
  sensitive   = true
}

variable "grokx_api_url" {
  description = "URL endpoint for the GrokX LLM API"
  type        = string
  default     = "https://api.grokx.ai/v1/chat/completions"
}