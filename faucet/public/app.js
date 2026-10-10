const form=document.querySelector("#claimForm");
const statusEl=document.querySelector("#status");
const responseEl=document.querySelector("#response");
const submit=document.querySelector("#submit");
const refInput=document.querySelector("#referral");
let widgetId=null;
const match=location.pathname.match(/^\/r\/([A-Za-z0-9_-]{5,24})$/);
const qs=new URLSearchParams(location.search);
const ref=match?.[1] || qs.get("ref") || "";
if (/^[a-zA-Z0-9_-]{5,24}$/.test(ref)) {
  refInput.value=ref;
  const banner=document.querySelector("#referred");
  banner.textContent="You're joining through a community invitation.";
  banner.hidden=false;
}
async function json(url,options){
  const res=await fetch(url,{cache:"no-store",...options});
  const body=await res.json();
  if(!res.ok) throw new Error(body.error || "Request failed");
  return body;
}
function setupCaptcha(sitekey){
  if(!sitekey) return;
  const script=document.createElement("script");
  script.src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
  script.async=true;
  script.onload=()=>{
    widgetId=window.turnstile.render("#captcha",{sitekey,theme:"dark"});
  };
  document.head.append(script);
}
async function init(){
  try{
    const s=await json("/api/status");
    document.querySelector("#desktop").href=s.desktopUrl;
    document.querySelector("#webwallet").href=s.webWalletUrl;
    statusEl.textContent=s.mode==="local_demo"
      ?"Local preview: test registrations only — no actual FEEL transfers"
      :s.open?"Registration pilot: pending review — payouts disabled"
      :"Coming soon — community faucet is being prepared; claims are not open yet.";
    submit.disabled=!s.open;
    submit.textContent=s.open?"Register for a FEEL claim":"Claims opening soon";
    setupCaptcha(s.turnstileSitekey);
  }catch{
    statusEl.textContent="Faucet connection unavailable. Please try later.";
  }
  try{
    const stats=await json("/api/stats");
    document.querySelector("#claims").textContent=stats.queuedClaims.toLocaleString();
    document.querySelector("#referrals").textContent=stats.queuedReferrals.toLocaleString();
  }catch{}
}
form.addEventListener("submit",async event=>{
  event.preventDefault();
  submit.disabled=true;responseEl.textContent="Submitting registration…";
  try{
    const captcha=widgetId!==null && window.turnstile ? window.turnstile.getResponse(widgetId):null;
    const body={address:document.querySelector("#address").value.trim(),referral:refInput.value,captcha};
    const result=await json("/api/register",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    responseEl.textContent=result.message;
    document.querySelector("#refUrl").textContent=result.referralUrl;
    document.querySelector("#refBox").hidden=false;
    document.querySelector("#copy").onclick=()=>navigator.clipboard.writeText(result.referralUrl);
    document.querySelector("#share").onclick=()=>{
      const txt="Your first FEEL starts here! Join the Feelcoin community. "+result.referralUrl;
      if(navigator.share) navigator.share({title:"Spread the Feels",text:txt,url:result.referralUrl}).catch(()=>{});
      else navigator.clipboard.writeText(txt);
    };
  }catch(err){responseEl.textContent=err.message;}
  finally{
    submit.disabled=false;
    if(widgetId!==null && window.turnstile) window.turnstile.reset(widgetId);
  }
});
init();
