#!/usr/bin/env python3
"""Emit only native-proved F8 final-edge options for the Android test consumer.

The complete original-graph candidate/negative ledger remains immutable in
Graph Studio. The partial Android cache is derived, SHA-bound, never marked
complete, and DOES NOT disable RoadPilot's F8 runtime discovery.
"""
import argparse, hashlib, json, os, tempfile
from pathlib import Path

def make_partial_cache(document, original_sha):
    if (document.get("schema")!="roadpilot.f8-final-directed-connections" or
        document.get("version")!=1 or
        document.get("productionPublication")!="BLOCKED" or
        document.get("sourceDiscoveryComplete") is not False or
        document.get("physicalRoadPerDirectionGlobalUniqueness")!="NOT_VERIFIED"):
        raise ValueError("Source-final original GraphStudio evidence is not an unpublished incomplete inventory")
    verified=document.get("connections",[])
    unknown=document.get("unresolvedSourceFinalEdges",[])
    if not verified or not isinstance(unknown,list):
        raise ValueError("No native verified source finals or missing unresolved ledger")
    keys=set()
    matched=set()
    for item in verified:
        k=(item["sourceRegionId"],item["sourceFinalDirectedGraphId"])
        if k in keys:raise ValueError("Duplicate source final road")
        keys.add(k)
        proofs=item.get("originalSourceFinalTopologyProof")
        if not isinstance(proofs,dict) or not proofs:
            raise ValueError("Source final lacks original native terminal audit")
        for mode in item["sourceValhallaProvedModes"]:
            if proofs[mode]["status"]!="NO_OTHER_NATIVE_PHYSICAL_FORWARD_CONTINUATION":
                raise ValueError("Not an actual native terminal per mode")
        if not item["receiverOptions"]:raise ValueError("No verified receiver directed options")
        receiverids=set()
        for option in item["receiverOptions"]:
            bid=option["receiverFirstDirectedGraphId"]
            if bid in receiverids:raise ValueError("Repeated native receiver branch")
            receiverids.add(bid)
            if (option["directedPhysicalGeometry"]["status"]!="FORWARD_CONTINUOUS" or
                not option["travelModes"]):
                raise ValueError("Receiver branch not verified")
            for mode in option["travelModes"]:
                if mode not in item["sourceValhallaProvedModes"]:
                    raise ValueError("Receiving mode unsupported on original source")
                proof=option["originalReceiverValhallaTripLeg"][mode]
                if (not proof.get("verified") or
                    proof.get("actualFirstDirectedGraphId")!=bid or
                    proof["originalTripLegDirectedGraphIds"][0]!=bid):
                    raise ValueError("Receiver original native first edge not proved")
            matched.add((k,bid))
    unresolved_keys=set()
    for item in unknown:
        key=(item["sourceRegionId"],item["sourceFinalDirectedGraphId"])
        if key in keys or key in unresolved_keys:
            raise ValueError("Original GraphStudio unresolved-source inventory repeats final")
        unresolved_keys.add(key)
        if item["mustNotCreateConnection"] is not True:
            raise ValueError("Unknown original source must be blocked from Android connection use")
    result={key:val for key,val in document.items()
       if key not in ("unresolvedSourceFinalEdges","counts")}
    result["unresolvedSourceFinalEdges"]=[]
    result["originalUnpublishedFullNativeLedgerSHA256"]="sha256:"+original_sha
    result["originalUnpublishedFullNativeUnresolvedCount"]=len(unknown)
    result["consumerCacheScope"]="VERIFIED_NATIVE_FINAL_EDGE_CONNECTIONS_ONLY_RUNTIME_DISCOVERY_REMAINS_ENABLED"
    result["sourceDiscoveryComplete"]=False
    result["productionPublication"]="BLOCKED"
    result["counts"]={"nativeVerifiedSourceDirectedIDs":len(keys),
        "nativeVerifiedReceivingDirectedOptions":len(matched),
        "unresolvedOriginalNativeCandidateIDsRetainedInGraphStudioEvidence":len(unresolved_keys)}
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("Refuse to replace an immutable Android test catalog")
    raw=args.source.read_bytes()
    d=json.loads(raw)
    out=make_partial_cache(d,hashlib.sha256(raw).hexdigest())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile("w",delete=False,
        dir=args.output.parent,prefix=".f8-android-partial-",encoding="utf8") as f:
        staged=Path(f.name)
        json.dump(out,f,separators=(",",":"),allow_nan=False)
        f.write("\n")
    try:os.link(staged,args.output)
    finally:staged.unlink(missing_ok=True)
    data=args.output.read_bytes()
    if len(data)>3_000_000:
        raise ValueError("Source-final Android test cache exceeds bounded native Android parser")
    print("F8_ANDROID_PARTIAL_TEST_CACHE",args.output,
          "sha256:"+hashlib.sha256(data).hexdigest(),
          "bytes",len(data),"source",len(out["connections"]),
          "options",out["counts"]["nativeVerifiedReceivingDirectedOptions"],
          flush=True)


if __name__=="__main__":
    try: main()
    except (ValueError,OSError,TypeError,KeyError,IndexError) as error:
        raise SystemExit("F8_ANDROID_PARTIAL_CACHE_ERROR: "+str(error)[:400])
