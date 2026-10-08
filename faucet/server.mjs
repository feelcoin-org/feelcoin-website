import {createServer} from "node:http";
import {readFile, mkdir} from "node:fs/promises";
import {fileURLToPath} from "node:url";
import {dirname, join, extname} from "node:path";
import {randomBytes, createHmac} from "node:crypto";
import {DatabaseSync} from "node:sqlite";

const root = dirname(fileURLToPath(import.meta.url));
const host = process.env.FAUCET_HOST || "127.0.0.1";
const port = Number(process.env.PORT || 8787);
const publicOrigin = process.env.FAUCET_PUBLIC_ORIGIN || "http://127.0.0.1:" + port;
const isLoopback = host === "127.0.0.1" || host === "::1" || host === "localhost";
const demo = process.env.FAUCET_DEMO_MODE === "true" && isLoopback;
const pilotRequested = process.env.FAUCET_PILOT_ENABLED === "true";
const captchaSecret = process.env.TURNSTILE_SECRET_KEY || "";
const captchaSitekey = process.env.TURNSTILE_SITE_KEY || "";
const ipSalt = process.env.FAUCET_IP_HASH_SECRET || "";
// A pilot requires real CAPTCHA and stable, private hashing of IP addresses.
// Deliberately no wallet RPC, hot-wallet key, or on-chain payout capability yet.
const pilot = pilotRequested && !demo && Boolean(captchaSecret && captchaSitekey && ipSalt);
if (pilotRequested && !pilot) throw new Error("Pilot requires Turnstile keys and FAUCET_IP_HASH_SECRET");
if (demo && !isLoopback) throw new Error("Demo is localhost-only");
if (process.env.FAUCET_LIVE_PAYOUTS === "true") throw new Error("Live payouts are intentionally not implemented");
const accepting = pilot || demo;
const dataDir = process.env.FAUCET_DATA_DIR || join(root,"data");
await mkdir(dataDir,{recursive:true,mode:0o700});
const db = new DatabaseSync(join(dataDir,"faucet.sqlite"));
db.exec("PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;");
db.exec("CREATE TABLE IF NOT EXISTS participants(address TEXT PRIMARY KEY, ref_code TEXT UNIQUE NOT NULL, created_at INTEGER NOT NULL, ip_hash TEXT NOT NULL)");
db.exec("CREATE TABLE IF NOT EXISTS claims(id TEXT PRIMARY KEY,address TEXT NOT NULL,ip_hash TEXT NOT NULL, created_at INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'pending_review')");
db.exec("CREATE INDEX IF NOT EXISTS claims_address_time ON claims(address,created_at)");
db.exec("CREATE INDEX IF NOT EXISTS claims_ip_time ON claims(ip_hash,created_at)");
db.exec("CREATE TABLE IF NOT EXISTS referrals(newcomer_address TEXT PRIMARY KEY,inviter_address TEXT NOT NULL,created_at INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'pending_review')");
const q = {
  user:db.prepare("SELECT address,ref_code,ip_hash FROM participants WHERE address=?"),
  ref:db.prepare("SELECT address,ip_hash FROM participants WHERE ref_code=?"),
  code:db.prepare("SELECT 1 FROM participants WHERE ref_code=?"),
  lastWallet:db.prepare("SELECT 1 FROM claims WHERE address=? AND created_at>=? LIMIT 1"),
  lastIp:db.prepare("SELECT 1 FROM claims WHERE ip_hash=? AND created_at>=? LIMIT 1"),
  addUser:db.prepare("INSERT INTO participants(address,ref_code,created_at,ip_hash) VALUES(?,?,?,?)"),
  addClaim:db.prepare("INSERT INTO claims(id,address,ip_hash,created_at) VALUES(?,?,?,?)"),
  addReferral:db.prepare("INSERT INTO referrals(newcomer_address,inviter_address,created_at) VALUES(?,?,?)"),
  claims:db.prepare("SELECT COUNT(*) AS n FROM claims"),
  refs:db.prepare("SELECT COUNT(*) AS n FROM referrals"),
};
const mime = {".html":"text/html; charset=utf-8",".css":"text/css; charset=utf-8",".js":"text/javascript; charset=utf-8",".webp":"image/webp"};
function respond(res,code,data) {
  const value=JSON.stringify(data);
  res.writeHead(code,{"Content-Type":"application/json; charset=utf-8","Content-Length":Buffer.byteLength(value),"Cache-Control":"no-store"});
  res.end(value);
}
function validAddress(address) {
  // Format-only guard; full Feelcoin address checksum validation is a pre-payout requirement.
  return typeof address === "string" && address.length >= 90 && address.length <= 110
    && /^[1-9A-HJ-NP-Za-km-z]+$/.test(address);
}
function ipHash(ip) {
  return createHmac("sha256",ipSalt || "LOCAL_DEMO_ONLY").update(ip).digest("hex");
}
async function captchaOkay(token,ip) {
  if(demo) return true;
  if (!pilot || typeof token !== "string" || token.length > 2048 || !token) return false;
  try {
    const params = new URLSearchParams({secret:captchaSecret,response:token,remoteip:ip});
    const result = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify",{
      method:"POST",body:params,signal:AbortSignal.timeout(6000)
    });
    const json=await result.json();
    return json.success === true && json.hostname === new URL(publicOrigin).hostname;
  } catch {return false;}
}
const htmlFiles = new Map([["/","index.html"],["/styles.css","styles.css"],["/app.js","app.js"]]);
async function serveStatic(res,path) {
  const file = htmlFiles.get(path) || (/^\/r\/[a-zA-Z0-9_-]{5,24}$/.test(path) ? "index.html":null);
  if(!file){respond(res,404,{error:"Not found"});return;}
  try {
    const body=await readFile(join(root,"public",file));
    res.writeHead(200,{"Content-Type":mime[extname(file)],"Cache-Control":"no-store"});
    res.end(body);
  } catch {respond(res,500,{error:"Asset unavailable"});}
}
async function readJson(req){
  const ct=req.headers["content-type"] || "";
  if (!ct.toLowerCase().startsWith("application/json")) throw new Error("JSON required");
  const chunks=[];let size=0;
  for await(const chunk of req){
    size+=chunk.length;
    if(size>4096) throw new Error("Request too large");
    chunks.push(chunk);
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}
function newCode() {
  let code;
  do {code = randomBytes(6).toString("base64url");}while(q.code.get(code));
  return code;
}
async function register(req,res){
  if(!accepting){respond(res,503,{error:"Faucet claims are not open yet. No coins are being distributed."});return;}
  if(req.headers.origin && req.headers.origin !== publicOrigin){respond(res,403,{error:"Origin mismatch"});return;}
  let body;
  try{body=await readJson(req);}catch{respond(res,400,{error:"Invalid JSON"});return;}
  const address=typeof body.address==="string" ? body.address.trim():"";
  const referral=typeof body.referral==="string" ? body.referral.trim():"";
  if(!validAddress(address)){respond(res,400,{error:"Invalid FEEL address format"});return;}
  if(referral && !/^[a-zA-Z0-9_-]{5,24}$/.test(referral)){respond(res,400,{error:"Invalid referral code"});return;}
  const ip=req.socket.remoteAddress || "unknown"; // never trust spoofable X-Forwarded-For
  if(!await captchaOkay(body.captcha,ip)){respond(res,403,{error:"Captcha verification required"});return;}
  const hash=ipHash(ip), now=Date.now(), cutoff=now-86400000;
  try {
    db.exec("BEGIN IMMEDIATE");
    // One request per wallet AND per IP per 24h; referrals are held for review.
    if(q.lastWallet.get(address,cutoff) || q.lastIp.get(hash,cutoff)){
      db.exec("ROLLBACK");respond(res,429,{error:"Daily claim limit reached"});return;
    }
    let participant=q.user.get(address);
    let inviter;
    if(referral && !participant){
      inviter=q.ref.get(referral);
      if(!inviter){db.exec("ROLLBACK");respond(res,400,{error:"Referral code not found"});return;}
      if(inviter.address===address || inviter.ip_hash===hash){
        db.exec("ROLLBACK");respond(res,400,{error:"Self-referrals are not eligible"});return;
      }
    }
    if(!participant) {
      const refCode=newCode();
      q.addUser.run(address,refCode,now,hash);
      participant={ref_code:refCode};
    }
    const claimId=randomBytes(12).toString("hex");
    q.addClaim.run(claimId,address,hash,now);
    if(inviter) q.addReferral.run(address,inviter.address,now);
    db.exec("COMMIT");
    respond(res,202,{
      status:"pending_review",claimId,referralCode:participant.ref_code,
      referralUrl:"https://faucet.feelcoin.org/r/"+participant.ref_code,
      referred:!!inviter,
      message:"Registration received. No FEEL has been transferred. Both referral rewards require verification and funded budget."
    });
  }catch(e){
    try{db.exec("ROLLBACK");}catch{}
    console.error("claim processing error",e?.message);
    respond(res,500,{error:"Unable to queue claim"});
  }
}
const server=createServer(async(req,res)=>{
  res.setHeader("X-Content-Type-Options","nosniff");
  res.setHeader("Referrer-Policy","no-referrer");
  res.setHeader("X-Frame-Options","DENY");
  res.setHeader("Content-Security-Policy","default-src 'none'; img-src 'self' https://feelcoin.org; script-src 'self' https://challenges.cloudflare.com; style-src 'self'; connect-src 'self' https://challenges.cloudflare.com; frame-src https://challenges.cloudflare.com; base-uri 'none'; form-action 'self'");
  const path=new URL(req.url || "/",publicOrigin).pathname;
  if(req.method==="GET" && path==="/api/status") return respond(res,200,{
    open:accepting,mode:demo?"local_demo":pilot?"registration_pilot":"closed",
    payoutsEnabled:false,rewards:"pending_review",
    turnstileSitekey:pilot?captchaSitekey:null,
    desktopUrl:"https://github.com/feelcoin-org/feelcoin-desktop/releases/tag/v0.1.0-alpha",
    webWalletUrl:"https://wallet.feelcoin.org",
    budgetStatus:"awaiting_verified_emission_and_funding"
  });
  if(req.method==="GET" && path==="/api/stats") return respond(res,200,{
    queuedClaims:q.claims.get().n,queuedReferrals:q.refs.get().n,
    paidFeel:"0",budgetFeel:null
  });
  if(req.method==="POST" && path==="/api/register")return register(req,res);
  if(req.method==="GET")return serveStatic(res,path);
  respond(res,405,{error:"Method not allowed"});
});
server.listen(port,host,()=>console.log("Feelcoin Faucet foundation listening on "+host+":"+port+" | "+(demo?"LOCAL DEMO":pilot?"PILOT":"CLOSED")));
