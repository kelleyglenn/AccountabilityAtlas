terraform {
  backend "s3" {
    bucket         = "accountabilityatlas-tfstate"
    key            = "prod/terraform.tfstate"
    region         = "us-east-2"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}
