data "aws_secretsmanager_secret_version" "jwt_private_key" {
  secret_id = "${var.project_name}/jwt-private-key"
}

data "aws_secretsmanager_secret_version" "youtube_api_key" {
  secret_id = "${var.project_name}/youtube-api-key"
}

data "aws_secretsmanager_secret_version" "mapbox_token" {
  secret_id = "${var.project_name}/mapbox-access-token"
}

data "aws_secretsmanager_secret_version" "admin_password_hash" {
  secret_id = "${var.project_name}/admin-password-hash"
}
