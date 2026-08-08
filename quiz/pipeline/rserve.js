// 支持 HTTP Range 的静态服务器。
// python -m http.server 不支持 Range，pmtiles 会退化成整包下载，
// 上一轮就因此把 29.6MB 全下了一遍，误判成"首屏很慢"。
const http=require("http"),fs=require("fs"),path=require("path");
const ROOT=process.argv[2]||".",PORT=+(process.argv[3]||8770);
const MIME={".html":"text/html;charset=utf-8",".js":"application/javascript",".css":"text/css",
  ".json":"application/json",".pmtiles":"application/octet-stream",".png":"image/png"};
http.createServer((req,res)=>{
  const u=decodeURIComponent(req.url.split("?")[0]);
  const p=path.join(ROOT,u==="/"?"/index.html":u);
  fs.stat(p,(e,st)=>{
    if(e||!st.isFile()){res.writeHead(404);return res.end("404");}
    const type=MIME[path.extname(p)]||"application/octet-stream";
    const range=req.headers.range;
    if(range){
      const m=/bytes=(\d*)-(\d*)/.exec(range);
      const start=m[1]?+m[1]:0, end=m[2]?+m[2]:st.size-1;
      res.writeHead(206,{"Content-Type":type,"Content-Range":`bytes ${start}-${end}/${st.size}`,
        "Accept-Ranges":"bytes","Content-Length":end-start+1});
      fs.createReadStream(p,{start,end}).pipe(res);
    } else {
      res.writeHead(200,{"Content-Type":type,"Content-Length":st.size,"Accept-Ranges":"bytes"});
      fs.createReadStream(p).pipe(res);
    }
  });
}).listen(PORT,()=>console.log("serving "+ROOT+" on :"+PORT));
