'use client';

import { useEffect, useRef, useState } from 'react';
import { useTheme } from 'next-themes';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import Graph from 'graphology';
import forceAtlas2 from 'graphology-layout-forceatlas2';
import { ArrowsClockwise, Minus, Pause, Play, Plus } from '@phosphor-icons/react';
import { Hint } from './bits';
import type { Constellation, ConstellationNode } from '@/services/yojak';

interface SceneAPI { select: (id: string | null) => void; zoom: (factor: number) => void; reset: () => void; rotate: (enabled: boolean) => void }

function layout(data: Constellation) {
    const graph = new Graph({ type: 'undirected' });
    data.nodes.forEach((n, i) => {
        const angle = i * 2.39996, radius = Math.sqrt((i + 1) / data.nodes.length);
        graph.addNode(n.id, { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius });
    });
    data.edges.forEach((e) => {
        if (graph.hasNode(e.source) && graph.hasNode(e.target) && !graph.hasEdge(e.source, e.target))
            graph.addEdge(e.source, e.target, { weight: Math.min(e.weight, 5) });
    });
    forceAtlas2.assign(graph, { iterations: 150, settings: {
        ...forceAtlas2.inferSettings(graph), gravity: 2, scalingRatio: 3, barnesHutOptimize: true,
    } });
    const points = data.nodes.map((n) => graph.getNodeAttributes(n.id));
    const xs = points.map((p) => p.x), ys = points.map((p) => p.y);
    const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2;
    const extent = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys), 1);
    // Preserve measured neighbourhoods; depth separates overlapping nodes.
    return new Map(data.nodes.map((n, i) => [n.id, new THREE.Vector3(
        (points[i].x - cx) / extent * 7, (points[i].y - cy) / extent * 7, Math.sin(i * 2.39996) * 2.8,
    )]));
}

export function SkillNetworkScene({ data, selectedId, onSelect }: {
    data: Constellation; selectedId: string | null; onSelect: (node: ConstellationNode) => void;
}) {
    const host = useRef<HTMLDivElement>(null), api = useRef<SceneAPI | null>(null);
    const onSelectRef = useRef(onSelect), currentSelection = useRef(selectedId);
    const labelElements = useRef(new Map<string, HTMLButtonElement>());
    const { resolvedTheme } = useTheme();
    const [unavailable, setUnavailable] = useState(false), [rotating, setRotating] = useState(false), [ready, setReady] = useState(false);
    onSelectRef.current = onSelect;
    currentSelection.current = selectedId;
    const prominent = [...data.nodes].sort((a, b) => b.postings - a.postings).slice(0, 6);
    const selected = data.nodes.find((n) => n.id === selectedId);
    const connectedIds = new Set(data.edges.filter((edge) => edge.source === selectedId || edge.target === selectedId).flatMap((edge) => [edge.source, edge.target]));
    const labels = selected ? [selected, ...data.nodes.filter((node) => node.id !== selectedId && connectedIds.has(node.id)).sort((a, b) => b.postings - a.postings).slice(0, 5)] : prominent;

    useEffect(() => {
        if (!host.current || !data.nodes.length) return;
        const container = host.current;
        let renderer: THREE.WebGLRenderer;
        setReady(false);
        setUnavailable(false);
        try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true }); }
        catch { setUnavailable(true); return; }
        const dark = resolvedTheme === 'dark';
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
        renderer.setClearColor(0x000000, 0);
        renderer.outputColorSpace = THREE.SRGBColorSpace;
        renderer.domElement.setAttribute('aria-label', '3D network of skills and occupations');
        renderer.domElement.setAttribute('role', 'img');
        renderer.domElement.style.touchAction = 'pan-y';
        container.appendChild(renderer.domElement);
        const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
        camera.position.set(0, 0, 13.5);
        const controls = new OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.enablePan = false;
        controls.enableZoom = false;
        controls.minDistance = 6;
        controls.maxDistance = 20;
        controls.autoRotateSpeed = 0.35;
        controls.touches.ONE = THREE.TOUCH.ROTATE;
        const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
        controls.autoRotate = !motion.matches;
        setRotating(!motion.matches);
        scene.add(new THREE.HemisphereLight(0xffffff, dark ? 0x273833 : 0x849ba0, 2.2));
        const light = new THREE.DirectionalLight(0xffffff, 3);
        light.position.set(-4, 6, 8);
        scene.add(light);
        const positions = layout(data), geometry = new THREE.SphereGeometry(1, 16, 12);
        const meshes = new Map<string, THREE.Mesh<THREE.SphereGeometry, THREE.MeshStandardMaterial>>();
        const maxPostings = Math.max(...data.nodes.map((n) => n.postings), 1);
        data.nodes.forEach((node) => {
            const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({
                color: node.kind === 'occupation' ? 0xd49a29 : 0x108b80, metalness: 0.28, roughness: 0.28,
            }));
            mesh.position.copy(positions.get(node.id)!);
            mesh.scale.setScalar(0.055 + Math.sqrt(node.postings / maxPostings) * 0.15);
            mesh.userData.node = node;
            meshes.set(node.id, mesh);
            scene.add(mesh);
        });
        const validEdges = data.edges.filter((e) => positions.has(e.source) && positions.has(e.target));
        const edgePositions = new Float32Array(validEdges.length * 6), edgeColors = new Float32Array(validEdges.length * 6);
        validEdges.forEach((e, i) => {
            positions.get(e.source)!.toArray(edgePositions, i * 6);
            positions.get(e.target)!.toArray(edgePositions, i * 6 + 3);
        });
        const edgeGeometry = new THREE.BufferGeometry();
        edgeGeometry.setAttribute('position', new THREE.BufferAttribute(edgePositions, 3));
        edgeGeometry.setAttribute('color', new THREE.BufferAttribute(edgeColors, 3));
        const edgeMaterial = new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: dark ? 0.5 : 0.42 });
        scene.add(new THREE.LineSegments(edgeGeometry, edgeMaterial));
        let dirty = true;
        const applySelection = (id: string | null) => {
            const neighbors = new Set<string>();
            validEdges.forEach((e) => { if (e.source === id) neighbors.add(e.target); if (e.target === id) neighbors.add(e.source); });
            meshes.forEach((mesh, nodeId) => {
                const focus = !id || nodeId === id || neighbors.has(nodeId);
                mesh.material.color.set(focus ? (mesh.userData.node.kind === 'occupation' ? 0xd49a29 : 0x108b80) : (dark ? 0x334043 : 0xc8d2d7));
                mesh.material.emissive.set(nodeId === id ? 0x06473e : 0x000000);
            });
            validEdges.forEach((e, i) => {
                const connected = e.source === id || e.target === id;
                const color = new THREE.Color(connected ? 0x108b80 : dark ? 0x536265 : id ? 0xdfe5e8 : 0x9baeb4);
                color.toArray(edgeColors, i * 6); color.toArray(edgeColors, i * 6 + 3);
            });
            edgeGeometry.attributes.color.needsUpdate = true;
            dirty = true;
        };
        applySelection(currentSelection.current);
        api.current = {
            select: applySelection,
            rotate: (enabled) => { controls.autoRotate = enabled; dirty = true; },
            zoom: (factor) => { camera.position.multiplyScalar(factor).clampLength(6, 20); dirty = true; },
            reset: () => { camera.position.set(0, 0, 13.5); controls.target.set(0, 0, 0); controls.update(); dirty = true; },
        };
        const resize = new ResizeObserver(() => {
            const width = container.clientWidth, height = container.clientHeight;
            if (!width || !height) return;
            camera.aspect = width / height;
            camera.fov = width < height ? 53 : 42;
            camera.updateProjectionMatrix();
            renderer.setSize(width, height);
            dirty = true;
        });
        resize.observe(container);
        let visible = true;
        const intersection = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; dirty = true; });
        intersection.observe(container);
        controls.addEventListener('change', () => { dirty = true; });
        const preferenceChanged = () => { if (motion.matches) { controls.autoRotate = false; setRotating(false); } dirty = true; };
        motion.addEventListener('change', preferenceChanged);
        const raycaster = new THREE.Raycaster(), pointer = new THREE.Vector2();
        let downX = 0, downY = 0;
        const pointerDown = (e: PointerEvent) => { downX = e.clientX; downY = e.clientY; };
        const pointerUp = (e: PointerEvent) => {
            if (Math.hypot(e.clientX - downX, e.clientY - downY) > 6) return;
            const bounds = renderer.domElement.getBoundingClientRect();
            pointer.set((e.clientX - bounds.left) / bounds.width * 2 - 1, -(e.clientY - bounds.top) / bounds.height * 2 + 1);
            raycaster.setFromCamera(pointer, camera);
            const hit = raycaster.intersectObjects([...meshes.values()])[0];
            if (hit) onSelectRef.current(hit.object.userData.node);
        };
        const contextLost = (e: Event) => { e.preventDefault(); setUnavailable(true); };
        renderer.domElement.addEventListener('pointerdown', pointerDown);
        renderer.domElement.addEventListener('pointerup', pointerUp);
        renderer.domElement.addEventListener('webglcontextlost', contextLost);
        let frame = 0;
        const projected = new THREE.Vector3();
        const tick = () => {
            frame = requestAnimationFrame(tick);
            if (!visible || document.hidden) return;
            controls.update();
            if (!dirty && !controls.autoRotate) return;
            renderer.render(scene, camera);
            const occupied: { x: number; y: number; width: number; height: number }[] = [];
            [...labelElements.current].sort(([a], [b]) => a === currentSelection.current ? -1 : b === currentSelection.current ? 1 : 0).forEach(([id, element]) => {
                const mesh = meshes.get(id);
                if (!mesh) return;
                projected.copy(mesh.position).project(camera);
                const x = (projected.x * 0.5 + 0.5) * container.clientWidth + 18;
                const y = (-projected.y * 0.5 + 0.5) * container.clientHeight - 20;
                const width = element.offsetWidth, height = element.offsetHeight;
                const rect = { x: x - width / 2, y: y - height / 2, width, height };
                const overlaps = occupied.some((r) => rect.x < r.x + r.width + 6 && rect.x + width + 6 > r.x && rect.y < r.y + r.height + 6 && rect.y + height + 6 > r.y);
                const clipped = rect.x < 12 || rect.x + width > container.clientWidth - 12 || rect.y < 65 || rect.y + height > container.clientHeight - 70 || projected.z > 1;
                element.style.left = `${x}px`;
                element.style.top = `${y}px`;
                element.style.visibility = clipped || overlaps ? 'hidden' : 'visible';
                if (!clipped && !overlaps) occupied.push(rect);
            });
            dirty = false;
        };
        tick();
        setReady(true);
        return () => {
            cancelAnimationFrame(frame); resize.disconnect(); intersection.disconnect();
            motion.removeEventListener('change', preferenceChanged);
            renderer.domElement.removeEventListener('pointerdown', pointerDown);
            renderer.domElement.removeEventListener('pointerup', pointerUp);
            renderer.domElement.removeEventListener('webglcontextlost', contextLost);
            controls.dispose(); geometry.dispose(); edgeGeometry.dispose(); edgeMaterial.dispose();
            meshes.forEach((mesh) => mesh.material.dispose());
            renderer.dispose(); renderer.domElement.remove(); api.current = null;
        };
    }, [data, resolvedTheme]);

    useEffect(() => { api.current?.select(selectedId); }, [selectedId, ready]);

    return <div className="relative h-full min-h-[280px] w-full overflow-hidden">
        <div ref={host} className="absolute inset-0 cursor-grab active:cursor-grabbing" data-testid="skill-network-canvas" />
        {!unavailable && ready && labels.map((node) => <button key={node.id} type="button" ref={(el) => {
            if (el) labelElements.current.set(node.id, el); else labelElements.current.delete(node.id);
        }} onClick={() => onSelect(node)} className="network-label" style={{ visibility: 'hidden' }} aria-pressed={selectedId === node.id} title={`${node.label}: ${node.postings.toLocaleString('en-IN')} postings`}>{node.label}</button>)}
        {unavailable && <div className="absolute inset-0 flex flex-col justify-center gap-3 px-6">
            <p className="text-sm text-muted-foreground">3D is unavailable on this device. Explore the same skill data below.</p>
            {prominent.map((node) => <button key={node.id} onClick={() => onSelect(node)} className="flex justify-between border-b py-2 text-left text-sm"><span>{node.label}</span><span className="tabular text-muted-foreground">{node.postings.toLocaleString('en-IN')}</span></button>)}
        </div>}
        {!unavailable && <div className="absolute bottom-4 right-4 z-20 flex gap-1.5" aria-label="Network controls">
            <Hint text="Zoom in"><button className="network-control" aria-label="Zoom in" disabled={!ready} onClick={() => api.current?.zoom(0.85)}><Plus size={17} /></button></Hint>
            <Hint text="Zoom out"><button className="network-control" aria-label="Zoom out" disabled={!ready} onClick={() => api.current?.zoom(1.15)}><Minus size={17} /></button></Hint>
            <Hint text="Reset view"><button className="network-control" aria-label="Reset view" disabled={!ready} onClick={() => api.current?.reset()}><ArrowsClockwise size={17} /></button></Hint>
            <Hint text={rotating ? 'Pause rotation' : 'Rotate network'}><button className="network-control" aria-label={rotating ? 'Pause rotation' : 'Rotate network'} aria-pressed={rotating} disabled={!ready} onClick={() => { api.current?.rotate(!rotating); setRotating(!rotating); }}>{rotating ? <Pause size={17} /> : <Play size={17} />}</button></Hint>
        </div>}
    </div>;
}
