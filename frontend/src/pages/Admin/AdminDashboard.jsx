import {useCallback,useEffect,useMemo,useState} from "react";
import {useNavigate} from "react-router-dom";
import "./AdminDashboard.css";

const API=import.meta.env.VITE_API_BASE_URL,T="admin_access_token",P="admin_profile";
const clear=()=>{localStorage.removeItem(T);localStorage.removeItem("admin_token_type");localStorage.removeItem(P)};
const dt=v=>v?new Date(v).toLocaleString("en-IN",{day:"2-digit",month:"short",year:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}):"—";

export default function AdminDashboard(){
 const nav=useNavigate(),[me,setMe]=useState(()=>{try{return JSON.parse(localStorage.getItem(P)||"{}")}catch{return{}}});
 const[counts,setCounts]=useState({}),[businesses,setBusinesses]=useState([]),[activity,setActivity]=useState([]),[search,setSearch]=useState(""),[error,setError]=useState(""),[loading,setLoading]=useState(true);
 const unauthorized=useCallback(()=>{clear();nav("/admin/login",{replace:true})},[nav]);
 const api=useCallback(async(url,opt={})=>{const t=localStorage.getItem(T);if(!t){unauthorized();throw Error("Admin session expired.")}const r=await fetch(url,{...opt,headers:{...(opt.headers||{}),Authorization:`Bearer ${t}`}});if(r.status===401){unauthorized();throw Error("Admin session expired.")}return r},[unauthorized]);
 const load=useCallback(async()=>{const[a,b]=await Promise.all([api(`${API}/api/admin/dashboard`),api(`${API}/api/admin/businesses`)]);const ad=await a.json(),bd=await b.json();if(!a.ok)throw Error(ad.detail||"Unable to load dashboard.");if(!b.ok)throw Error(bd.detail||"Unable to load businesses.");setCounts(ad.counts||{});setBusinesses(bd.businesses||[]);setActivity(ad.recent_activity||[]);if(ad.admin){setMe(ad.admin);localStorage.setItem(P,JSON.stringify(ad.admin))}},[api]);
 useEffect(()=>{load().catch(e=>setError(e.message)).finally(()=>setLoading(false))},[load]);
 const list=useMemo(()=>{const q=search.toLowerCase().trim();return !q?businesses:businesses.filter(x=>[x.business_name,x.business_type,x.email,x.mobile].filter(Boolean).some(v=>String(v).toLowerCase().includes(q)))},[businesses,search]);
 const logout=async()=>{try{const t=localStorage.getItem(T);if(t)await fetch(`${API}/api/admin/auth/logout`,{method:"POST",headers:{Authorization:`Bearer ${t}`}})}finally{clear();nav("/admin/login",{replace:true})}};
 if(loading)return <main className="adm-load">Loading administration...</main>;
 return <main className="adm">
  <aside><div className="adm-brand"><b>A</b><strong>AI Reviewer</strong></div><nav><button className="active">Overview</button><button onClick={()=>document.getElementById("businesses")?.scrollIntoView({behavior:"smooth"})}>Businesses</button>{me.role_name==="super_admin"&&<button onClick={()=>nav("/admin/staff")}>Staff</button>}<button onClick={()=>nav("/admin/audit-logs")}>Audit logs</button></nav><div className="adm-side-user"><span>{(me.full_name||"A")[0]}</span><div><b>{me.full_name}</b><small>{me.role_name==="super_admin"?"Super Administrator":"Staff"}</small></div><button onClick={logout}>Sign out</button></div></aside>
  <section className="adm-main"><header><div><small>ADMINISTRATION</small><h1>Platform overview</h1><p>Manage businesses and platform activity from one workspace.</p></div></header>
  {error&&<div className="adm-alert">{error}</div>}
  <section className="adm-metrics">{[["Customers",counts.customers],["Businesses",counts.businesses],["Dashboards",counts.dashboards],["Reviews",counts.reviews],["Websites",counts.websites],["Versions",counts.website_versions]].map(x=><article key={x[0]}><small>{x[0]}</small><b>{Number(x[1]||0).toLocaleString("en-IN")}</b></article>)}</section>
  <section className="adm-card" id="businesses"><header><div><small>BUSINESS WORKSPACE</small><h2>Businesses</h2><p>Open a business to manage its complete product data.</p></div><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search business..." /></header>
   <div className="adm-businesses">{list.map(b=><button key={b.business_id} onClick={()=>nav(`/admin/business/${b.business_id}`)}><span>{(b.business_name||"B")[0]}</span><div><b>{b.business_name}</b><small>{b.business_type||"Business"} · {b.email}</small></div><label>{b.dashboard_count} dashboards · {b.website_count} websites</label><i>→</i></button>)}{!list.length&&<p className="empty">No businesses found.</p>}</div>
  </section>
  <section className="adm-card"><header><div><small>SECURITY</small><h2>Recent administrative activity</h2></div></header><div className="activity">{activity.map(x=><article key={x.audit_id}><i/><div><b>{x.action}</b><p>{x.description}</p><small>{dt(x.created_at)}</small></div></article>)}{!activity.length&&<p className="empty">No activity yet.</p>}</div></section>
  </section>
 </main>
}
