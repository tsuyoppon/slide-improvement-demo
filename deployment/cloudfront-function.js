// CloudFront Function: ディレクトリアクセスを index.html にリダイレクト
function handler(event) {
    var request = event.request;
    var uri = request.uri;
    
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
