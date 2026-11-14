(function(root){
  function normalizedName(value){let s=String(value||'').toLowerCase().replace(/주식회사|유한회사|농업회사법인|㈜|\(주\)|\(유\)/g,'').replace(/[^가-힣a-z0-9]/g,'');for(const [a,b] of [['이디야커피','이디야'],['메가엠지씨커피','메가커피'],['메가mgc커피','메가커피'],['컴포즈커피','컴포즈'],['할리스커피','할리스']])s=s.replaceAll(a,b);return s;}
  function venueKey(row){return row.location?normalizedName(row.merchant)+'|'+row.location.lat+'|'+row.location.lng:'record|'+row.id;}
  function selectVenues(items,pool){const keys=new Set(items.map(venueKey)),groups=new Map();for(const row of pool){const key=venueKey(row);if(keys.has(key)){if(!groups.has(key))groups.set(key,{key,name:row.merchant,rows:[]});groups.get(key).rows.push(row);}}return [...groups.values()];}
  function roadKey(address){const match=String(address||'').match(/([가-힣0-9·.]+(?:대로|로|길))\s*(\d+(?:-\d+)?)/);return match?match[1]+'|'+match[2]:null;}
  function profileFor(row,profiles){const name=normalizedName(row.matched_merchant||row.merchant),location=row.location;if(!location)return null;const id=location.evidence_url?.match(/^https:\/\/place\.map\.kakao\.com\/(\d+)$/)?.[1];const valid=p=>p&&normalizedName(p.name)===name&&Math.abs(p.location?.lat-location.lat)<.001&&Math.abs(p.location?.lng-location.lng)<.001;if(id)return valid(profiles[id])?profiles[id]:null;const road=roadKey(row.address);if(!road)return null;const matches=Object.values(profiles).filter(p=>valid(p)&&roadKey(p.address)===road);return matches.length===1?matches[0]:null;}
  function menuDate(menu,profile){return (menu.source_updated_at||profile.menu_updated_at||'').slice(0,10);}
  function staleMenu(menu,profile,today=Date.now()){const date=menuDate(menu,profile);return date?today-new Date(date+'T00:00:00+09:00').getTime()>365*86400000:true;}
  const api={normalizedName,venueKey,selectVenues,profileFor,menuDate,staleMenu};if(typeof module!=='undefined')module.exports=api;root.MealRestaurants=api;
})(typeof window!=='undefined'?window:globalThis);
