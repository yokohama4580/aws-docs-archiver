#!/usr/bin/env python3
"""
AWS OIDC認証セットアップスクリプト

GitHubからAWSへのOIDC認証に必要なIAMリソースを作成するCDKスクリプト
"""

from aws_cdk import (
    Stack,
    aws_iam as iam,
    CfnOutput,
)
from constructs import Construct


class GithubOidcStack(Stack):
    """
    GitHubからAWSへのOIDC認証セットアップ用スタック
    """
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # GitHub OIDCプロバイダの作成
        github_provider = iam.OpenIdConnectProvider(
            self, "GitHubProvider",
            url="https://token.actions.githubusercontent.com",
            client_ids=["sts.amazonaws.com"],
        )

        # 開発環境用のIAMロール
        dev_role = iam.Role(
            self, "GitHubActionsDevRole",
            role_name="GitHubActionsDevRole",
            assumed_by=iam.WebIdentityPrincipal(
                github_provider.open_id_connect_provider_arn,
                conditions={
                    "StringLike": {
                        "token.actions.githubusercontent.com:sub": "repo:yokohama4580/aws-docs-archiver:ref:refs/heads/main"
                    }
                }
            )
        )

        # CDKデプロイに必要なポリシーをアタッチ
        dev_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess")
        )

        # 本番環境用のIAMロール
        prod_role = iam.Role(
            self, "GitHubActionsProdRole",
            role_name="GitHubActionsProdRole",
            assumed_by=iam.WebIdentityPrincipal(
                github_provider.open_id_connect_provider_arn,
                conditions={
                    "StringLike": {
                        "token.actions.githubusercontent.com:sub": "repo:yokohama4580/aws-docs-archiver:ref:refs/heads/main"
                    },
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
                    }
                }
            )
        )

        # 本番環境用のポリシー（より制限的にすべき）
        prod_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess")
        )

        # 出力値の定義
        CfnOutput(
            self, "DevRoleArn",
            value=dev_role.role_arn,
            description="開発環境用GitHubActionsのロールARN"
        )

        CfnOutput(
            self, "ProdRoleArn",
            value=prod_role.role_arn,
            description="本番環境用GitHubActionsのロールARN"
        )


# スタンドアロン実行用のコード
if __name__ == "__main__":
    from aws_cdk import App
    
    app = App()
    GithubOidcStack(app, "GitHubOidcStack")
    app.synth()