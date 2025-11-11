// CloudFront Function: ログインリダイレクトとディレクトリアクセスをハンドリング
function handler(event) {
    var request = event.request;
    var uri = request.uri;

    // /login へのショートカットを Cognito Hosted UI にリダイレクト
    if (uri === '/login' || uri === '/login/') {
        var cognitoLoginUrl = 'https://us-east-1i9cyurmhe.auth.us-east-1.amazoncognito.com/login?client_id=7bmla7ef7gn54hnik43b3glqa2&response_type=code&scope=email+openid+phone&redirect_uri=https://app2.rubato.co/auth/callback';
        return {
            statusCode: 302,
            statusDescription: 'Found',
            headers: {
                location: { value: cognitoLoginUrl },
                'cache-control': { value: 'no-store, no-cache, must-revalidate' }
            }
        };
    }

    // URIが / で終わる場合（ディレクトリアクセス）、index.html を追加
    if (uri.endsWith('/')) {
        request.uri = uri + 'index.html';
    }
    // URIに拡張子がない場合も index.html を追加
    else if (!uri.includes('.')) {
        request.uri = uri + '/index.html';
    }

    return request;
}
