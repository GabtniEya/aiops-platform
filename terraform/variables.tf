variable "region" {
  description = "Région AWS (aucune région en Tunisie ; Milan est la plus proche)"
  type        = string
  default     = "eu-south-1"
}

variable "cluster_name" {
  description = "Nom du cluster Kubernetes"
  type        = string
  default     = "aiops-cluster"
}

variable "kubernetes_version" {
  description = "Version de Kubernetes"
  type        = string
  default     = "1.31"
}

variable "node_instance_type" {
  description = "Type de machine des noeuds"
  type        = string
  default     = "t3.medium"
}