import test from "node:test";
import assert from "node:assert/strict";
import {spawn} from "node:child_process";
import {mkdtemp,rm} from "node:fs/promises";
import {tmpdir} from "node:os";
import {join,dirname} from "node:path";
import {fileURLToPath} from "node:url";
import {setTimeout as sleep} from "node:timers/promises";

const root=join(dirname(fileURLToPath(import.meta.url)),"..");
test("local demo queues a claim, rejects duplicates and never pays FEEL",async()=>{
  const dir=await mkdtemp(join(tmpdir(),"feelcoin-faucet-test-"));
  const port=19900+Math.floor(Math.random()*1000);
  const origin="http://127.0.0.1:"+port;
  const child=spawn(process.execPath,["server.mjs"],{
    cwd:root,env:{...process.env,FAUCET_DEMO_MODE:"true",FAUCET_HOST:"127.0.0.1",PORT:String(port),FAUCET_DATA_DIR:dir},
    stdio:["ignore","pipe","pipe"]
  });
  let output="";
  child.stderr.on("data",data=>{output+=data.toString();});
  child.stdout.on("data",data=>{output+=data.toString();});
  try{
    let ready=false;
    for(let i=0;i<60;i++){
      if(child.exitCode!==null) throw new Error("Server exited: "+output);
      try{const r=await fetch(origin+"/api/status",{signal:AbortSignal.timeout(500)});
        if(r.ok){ready=true;break;}}catch{}
      await sleep(100);
    }
    assert.ok(ready,"Server never started: "+output);
    const status=await(await fetch(origin+"/api/status")).json();
    assert.equal(status.mode,"local_demo");
    assert.equal(status.payoutsEnabled,false);
    const address="FA"+"A".repeat(93);
    const makeClaim=(wallet,extra={})=>fetch(origin+"/api/register",{
      method:"POST",headers:{"content-type":"application/json",origin},
      body:JSON.stringify({address:wallet,...extra})
    });
    let r=await makeClaim("invalid");
    assert.equal(r.status,400);
    r=await makeClaim(address);
    assert.equal(r.status,202,output);
    const claim=await r.json();
    assert.equal(claim.status,"pending_review");
    assert.ok(/^https:\/\/faucet\.feelcoin\.org\/r\/[A-Za-z0-9_-]{5,24}$/.test(claim.referralUrl));
    assert.match(claim.message,/No FEEL has been transferred/);
    r=await makeClaim(address);
    assert.equal(r.status,429);
    r=await fetch(origin+"/r/"+claim.referralCode);
    assert.equal(r.status,200);
    assert.match(await r.text(),/Made by the Community/);
    r=await makeClaim("FB"+"B".repeat(93),{referral:claim.referralCode});
    assert.equal(r.status,429,"Same IP cannot earn referral rewards");
    r=await fetch(origin+"/api/stats");
    const stats=await r.json();
    assert.equal(stats.queuedClaims,1);
    assert.equal(stats.queuedReferrals,0);
    assert.equal(stats.paidFeel,"0");
  }finally{
    child.kill("SIGTERM");
    await sleep(80);
    await rm(dir,{recursive:true,force:true});
  }
});
