import { useEffect,useState } from "react";
import { useNavigate } from "react-router-dom";
import "./AdminLogin.css";

const API_BASE_URL=import.meta.env.VITE_API_BASE_URL;
const TOKEN="admin_access_token", TYPE="admin_token_type", PROFILE="admin_profile";
const clear=()=>{localStorage.removeItem(TOKEN);localStorage.removeItem(TYPE);localStorage.removeItem(PROFILE)};

export default function AdminLogin(){
 const navigate=useNavigate();
 const [email,setEmail]=useState(""),[password,setPassword]=useState(""),[loading,setLoading]=useState(false),[checking,setChecking]=useState(true),[error,setError]=useState("");
 useEffect(()=>{const t=localStorage.getItem(TOKEN);if(!t){setChecking(false);return}
  fetch(`${API_BASE_URL}/api/admin/auth/me`,{headers:{Authorization:`Bearer ${t}`}})
   .then(r=>{if(r.ok)navigate("/admin",{replace:true});else clear()})
   .catch(()=>clear()).finally(()=>setChecking(false));
 },[navigate]);
 const submit=async e=>{e.preventDefault();setError("");setLoading(true);
  try{const r=await fetch(`${API_BASE_URL}/api/admin/auth/login`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email:email.trim().toLowerCase(),password})});
   const d=await r.json().catch(()=>({})); if(!r.ok)throw Error(d.detail||"Unable to sign in.");
   localStorage.setItem(TOKEN,d.access_token);localStorage.setItem(TYPE,d.token_type||"bearer");localStorage.setItem(PROFILE,JSON.stringify(d.admin||{}));navigate("/admin",{replace:true});
  }catch(e){setError(e.message||"Unable to sign in. Please try again.")}finally{setLoading(false)}
 };
 if(checking)return <main className="admin-login-page"><section className="admin-login-loading">Checking administrator session...</section></main>;
 return <main className="admin-login-page"><section className="admin-login-shell">
  <aside className="admin-login-brand-panel"><div className="admin-brand"><b>A</b> AI Reviewer</div>
   <div><small>ADMINISTRATION</small><h1>Manage your<br/>platform with<br/><span>confidence.</span></h1><p>A secure administrative workspace for managing businesses, staff, reviews and platform activity.</p></div>
   <footer>● Role-based access &nbsp; ● Protected sessions &nbsp; ● Audit-ready activity</footer>
  </aside>
  <section className="admin-login-panel"><div className="admin-login-form-wrap">
   <div className="admin-mobile-brand"><b>A</b> AI Reviewer</div>
   <header><small>ADMIN PORTAL</small><h2>Administrator sign in</h2><p>Sign in with your administrator account to continue.</p></header>
   <form onSubmit={submit}><label>Email address<input type="email" value={email} onChange={e=>{setEmail(e.target.value);setError("")}} autoComplete="username" required/></label>
    <label>Password<input type="password" value={password} onChange={e=>{setPassword(e.target.value);setError("")}} autoComplete="current-password" required/></label>
    {error&&<div className="admin-error">{error}</div>}
    <button disabled={loading}>{loading?"Signing in...":"Sign in"}</button>
   </form><p className="admin-note">Administrator access is separate from customer/business-owner login.</p>
  </div></section>
 </section></main>
}
