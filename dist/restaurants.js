(function(root){
  function normalizedName(value){let s=String(value||'').toLowerCase().replace(/주식회사|유한회사|농업회사법인|㈜|\(주\)|\(유\)/g,'').replace(/[^가-힣a-z0-9]/g,'');for(const [a,b] of [['이디야커피','이디야'],['메가엠지씨커피','메가커피'],['메가mgc커피','메가커피'],['컴포즈커피','컴포즈'],['할리스커피','할리스']])s=s.replaceAll(a,b);return s;}
  function venueKey(row){return row.location?normalizedName(row.merchant)+'|'+row.location.lat+'|'+row.location.lng:'record|'+row.id;}
  function selectVenues(items,pool){const keys=new Set(items.map(venueKey)),groups=new Map();for(const row of pool){const key=venueKey(row);if(keys.has(key)){if(!groups.has(key))groups.set(key,{key,name:row.merchant,rows:[]});groups.get(key).rows.push(row);}}return [...groups.values()];}
  function roadKey(address){const match=String(address||'').match(/([가-힣0-9·.]+(?:대로|로|길))\s*(\d+(?:-\d+)?)/);return match?match[1]+'|'+match[2]:null;}
  function profileFor(row,profiles,index){const name=normalizedName(row.matched_merchant||row.merchant),location=row.location;if(!location)return null;const id=location.evidence_url?.match(/^https:\/\/place\.map\.kakao\.com\/(\d+)$/)?.[1];const valid=p=>p&&normalizedName(p.name)===name&&Math.abs(p.location?.lat-location.lat)<.001&&Math.abs(p.location?.lng-location.lng)<.001;if(id)return valid(profiles[id])?profiles[id]:null;const road=roadKey(row.address);if(!road)return null;const matches=(index?(index.get(name)||[]):Object.values(profiles)).filter(p=>valid(p)&&roadKey(p.address)===road);return matches.length===1?matches[0]:null;}
  function menuDate(menu,profile){return (menu.source_updated_at||profile.menu_updated_at||'').slice(0,10);}
  function staleMenu(menu,profile,today=Date.now()){const date=menuDate(menu,profile);return date?today-new Date(date+'T00:00:00+09:00').getTime()>365*86400000:true;}
  const restaurantTypes=['소고기','돼지고기','고기구이','닭·오리','회·해산물','카페','베이커리·디저트','한식','중식','일식','양식','분식','아시아음식','기타','미분류'];
  function profileIndex(profiles){const result=new Map();for(const p of Object.values(profiles)){const name=normalizedName(p.name);if(!result.has(name))result.set(name,[]);result.get(name).push(p);}return result;}
  function classify(row,profile){
    const tags=new Set(),evidence=[],name=String(profile?.name||row.merchant||''),path=profile?.category_path?.join(' ')||profile?.category||'',menus=(profile?.menus||[]).map(m=>m.name).join(' ');
    const add=(tag,reason)=>{tags.add(tag);if(!evidence.includes(reason))evidence.push(reason);};
    // Registered categories take precedence over clues in an unverified name.
    for(const [tag,pattern] of [['카페',/카페|커피전문/],['베이커리·디저트',/베이커리|제과|간식|떡,한과|디저트/],['한식',/한식/],['중식',/중식|중국요리/],['일식',/일식/],['양식',/양식/],['분식',/분식/],['아시아음식',/아시아음식|동남아|인도음식/],['닭·오리',/닭요리|오리/],['회·해산물',/해물|생선|회$|장어/],['고기구이',/육류|고기|갈비|삼겹/],['소고기',/소고기|쇠고기|한우/],['돼지고기',/돼지|삼겹살/]])if(pattern.test(path))add(tag,'등록 업종');
    if(profile&&!tags.has('카페')&&!tags.has('베이커리·디저트')){
      if(/한우|소고기|쇠고기|소갈비|소불고기|안창살|차돌박이|꽃등심/.test(menus))add('소고기','등록 메뉴');
      if(/돼지|삼겹살|오겹살|목살|항정살|가브리살/.test(menus))add('돼지고기','등록 메뉴');
    }
    const named=[];
    const hint=(tag,pattern)=>{if(pattern.test(name)&&!tags.has(tag)){tags.add(tag);named.push(tag);}};
    if(!profile){
      hint('카페',/카페|커피|스타벅스|투썸플레이스|이디야|빽다방|컴포즈|할리스/);
      hint('베이커리·디저트',/베이커리|제과|파리바게뜨|파리바게트|뚜레쥬르/);
      hint('한식',/한식|한정식|국밥|설렁탕|곰탕|보리밥|쌈밥|감자탕|칼국수|순두부|백반/);
      hint('중식',/중화요리|중국집|짜장|짬뽕/);hint('일식',/일식|초밥|스시/);hint('양식',/이탈리안|파스타|피자/);hint('분식',/분식|김밥|떡볶이/);
    }
    if(!tags.has('카페')&&!tags.has('베이커리·디저트')){
      hint('소고기',/한우|소고기|쇠고기|소갈비/);hint('돼지고기',/돼지|삼겹|오겹|목살/);hint('닭·오리',/삼계탕|닭갈비|닭한마리|닭볶음|오리구이/);hint('회·해산물',/횟집|해물|생선|장어/);
    }
    if(named.length)evidence.push('상호 단서: '+[...new Set(named)].join('·'));
    if(!tags.size){if(profile)add('기타','등록 업종');else tags.add('미분류');}
    return {tags:restaurantTypes.filter(t=>tags.has(t)),provisional:named.length>0,evidence:evidence.join(' · ')||'분류 근거 없음'};
  }
  const api={normalizedName,venueKey,selectVenues,profileFor,menuDate,staleMenu,restaurantTypes,profileIndex,classify};if(typeof module!=='undefined')module.exports=api;root.MealRestaurants=api;
})(typeof window!=='undefined'?window:globalThis);
